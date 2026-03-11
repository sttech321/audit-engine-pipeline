'use client';

import { useState, useCallback } from 'react';
import { FileUpload } from '@/components/FileUpload';
import { KPIDisplay } from '@/components/KPIDisplay';
import { MintFlow } from '@/components/MintFlow';
import { ArrowLeft, Loader2, Download, FileImage, ShieldCheck, AlertTriangle, FileText } from 'lucide-react';
import Link from 'next/link';
import axios from 'axios';
import type { KPI, UploadMetadata, UploadResponse, VerificationStatus } from '@shared/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const BASE = `${API_URL}/api`;
const MAX_FILE_SIZE_BYTES = Number(process.env.NEXT_PUBLIC_MAX_FILE_SIZE_BYTES || 10_000_000_000);

// Use chunked upload for files >= 100 MB (faster, resumable)
const CHUNK_THRESHOLD = 100 * 1024 * 1024;
const CHUNK_SIZE = 20 * 1024 * 1024; // 20 MB - fewer HTTP requests for large files
const CONCURRENCY = 8; // Parallel chunk uploads, avoids network overload
const CHUNK_RETRY_ATTEMPTS = 3;
const CHUNK_RETRY_DELAY_MS = 1000;

interface UploadProgress {
    phase: 'uploading' | 'processing';
    pct: number;
    label: string;
    bytesLoaded?: number;
    bytesTotal?: number;
    chunksUploaded?: number;
    chunksTotal?: number;
}

export default function UploadPage() {
    const [uploadData, setUploadData] = useState<UploadResponse | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);

    const extractErrorMessage = (err: unknown): string => {
        const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
        if (typeof detail === 'string') return detail;
        if (detail && typeof detail === 'object' && 'error' in detail) {
            const error = detail.error;
            if (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string') {
                return error.message;
            }
            if (error && typeof error === 'object' && 'code' in error && typeof error.code === 'string') {
                return error.code;
            }
        }
        return err instanceof Error ? err.message : 'Failed to upload file';
    };

    const mapChunkedToUploadResponse = (r: {
        upload_id: string;
        file_info: { name: string; size: number; type?: string };
        kpis: KPI[];
        verification: VerificationStatus;
        file_hash: string;
        metadata: UploadMetadata;
    }): UploadResponse => ({
        uploadId: r.upload_id,
        fileInfo: { name: r.file_info.name, size: r.file_info.size, type: r.file_info.type ?? 'application/octet-stream' },
        kpis: r.kpis,
        verification: r.verification,
        fileHash: r.file_hash,
        metadata: r.metadata,
    });

    const uploadChunked = useCallback(async (file: File) => {
        const chunkSize = CHUNK_SIZE;
        const totalChunks = Math.ceil(file.size / chunkSize);
        if (totalChunks > 1000) throw new Error('File too large. Try increasing chunk size.');

        const initRes = await axios.post(`${BASE}/upload/chunked/init`, {
            filename: file.name,
            total_size: file.size,
            total_chunks: totalChunks,
            chunk_size: chunkSize,
        });
        const { upload_id, uploaded_chunks: existing } = initRes.data;

        const missing: number[] = [];
        for (let i = 0; i < totalChunks; i++) {
            if (!existing.includes(i)) missing.push(i);
        }

        let completedCount = existing.length;
        const formatMb = (n: number) => (n / 1024 / 1024).toFixed(1);

        const uploadChunkWithRetry = async (index: number): Promise<void> => {
            const start = index * chunkSize;
            const end = Math.min(start + chunkSize, file.size);
            const blob = file.slice(start, end);

            let lastErr: unknown;
            for (let attempt = 0; attempt < CHUNK_RETRY_ATTEMPTS; attempt++) {
                const form = new FormData();
                form.append('file', blob, file.name);
                try {
                    await axios.put(`${BASE}/upload/chunked/${upload_id}/chunk/${index}`, form, {
                        maxBodyLength: Infinity,
                        timeout: 0,
                    });
                    completedCount++;
                    const bytesLoaded = Math.min(completedCount * chunkSize, file.size);
                    setUploadProgress({
                        phase: 'uploading',
                        pct: (100 * completedCount) / totalChunks,
                        label: `Uploading file: ${formatMb(bytesLoaded)} MB of ${formatMb(file.size)} MB`,
                        bytesLoaded,
                        bytesTotal: file.size,
                        chunksUploaded: completedCount,
                        chunksTotal: totalChunks,
                    });
                    return;
                } catch (err) {
                    lastErr = err;
                    if (attempt < CHUNK_RETRY_ATTEMPTS - 1) {
                        await new Promise((r) => setTimeout(r, CHUNK_RETRY_DELAY_MS * (attempt + 1)));
                    }
                }
            }
            throw lastErr;
        };

        for (let b = 0; b < missing.length; b += CONCURRENCY) {
            const batch = missing.slice(b, b + CONCURRENCY);
            await Promise.all(batch.map((i) => uploadChunkWithRetry(i)));
        }

        setUploadProgress({
            phase: 'processing',
            pct: 0,
            label: 'Upload complete. Processing with RIM-OS v2...',
            bytesLoaded: file.size,
            bytesTotal: file.size,
            chunksUploaded: totalChunks,
            chunksTotal: totalChunks,
        });

        const completeRes = await axios.post(`${BASE}/upload/chunked/${upload_id}/complete`, null, {
            validateStatus: (s) => s === 200 || s === 202,
        });

        if (completeRes.status === 200 && completeRes.data?.file_info) {
            return mapChunkedToUploadResponse(completeRes.data);
        }

        const pollInterval = 1500;
        while (true) {
            const statusRes = await axios.get(`${BASE}/upload/chunked/${upload_id}/status`);
            const { status, processing_pct, result, error } = statusRes.data;

            setUploadProgress({
                phase: 'processing',
                pct: processing_pct ?? 0,
                label: `Processing with RIM-OS v2... ${(processing_pct ?? 0).toFixed(0)}%`,
                bytesLoaded: file.size,
                bytesTotal: file.size,
                chunksUploaded: totalChunks,
                chunksTotal: totalChunks,
            });

            if (status === 'completed' && result) {
                return mapChunkedToUploadResponse(result);
            }
            if (status === 'failed') {
                throw new Error(error || 'Processing failed');
            }

            await new Promise((r) => setTimeout(r, pollInterval));
        }
    }, []);

    const uploadSingle = useCallback(async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await axios.post<UploadResponse>(`${BASE}/upload`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            maxBodyLength: Infinity,
            maxContentLength: Infinity,
            timeout: 0,
            onUploadProgress: (e) => {
                const pct = e.total ? Math.round((100 * e.loaded) / e.total) : 0;
                const loadedMb = (e.loaded / 1024 / 1024).toFixed(1);
                const totalMb = e.total ? (e.total / 1024 / 1024).toFixed(1) : '?';
                const isUploadComplete = e.total && e.loaded >= e.total;
                setUploadProgress({
                    phase: isUploadComplete ? 'processing' : 'uploading',
                    pct,
                    label: isUploadComplete
                        ? 'Upload complete. Processing with RIM-OS v2...'
                        : `Uploading file: ${loadedMb} MB of ${totalMb} MB`,
                    bytesLoaded: e.loaded,
                    bytesTotal: e.total ?? undefined,
                });
            },
        });
        return response.data;
    }, []);

    const handleFileSelect = async (file: File) => {
        setIsUploading(true);
        setError(null);
        setUploadProgress(null);

        try {
            const useChunked = file.size >= CHUNK_THRESHOLD;
            const sizeMb = (file.size / 1024 / 1024).toFixed(1);
            setUploadProgress({
                phase: 'uploading',
                pct: 0,
                label: `Uploading file: 0 MB of ${sizeMb} MB`,
                bytesLoaded: 0,
                bytesTotal: file.size,
            });

            const result = useChunked
                ? await uploadChunked(file)
                : await uploadSingle(file);

            setUploadData(result);
        } catch (err: unknown) {
            setError(extractErrorMessage(err));
            console.error('Upload error:', err);
        } finally {
            setIsUploading(false);
            setUploadProgress(null);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
            <header className="border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                    <div className="flex items-center justify-between">
                        <Link
                            href="/"
                            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
                        >
                            <ArrowLeft className="w-5 h-5" />
                            <span>Back to Home</span>
                        </Link>
                        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                            Upload & Verify Audit
                        </h1>
                        <div className="w-24"></div>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
                {!uploadData ? (
                    <div className="max-w-3xl mx-auto">
                        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 space-y-8">
                            <div>
                                <h2 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                                    Upload Audit File
                                </h2>
                                <p className="text-gray-600 dark:text-gray-400">
                                    Pass97 will run your artifact through the canonical RIM-OS v2
                                    weight audit engine and return a compliance-ready summary.
                                </p>
                                <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-50/80 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                                    <ShieldCheck className="w-3 h-3" />
                                    <span>Powered by RIM-OS v2 (deterministic ledger)</span>
                                </div>
                            </div>

                            <div className="grid gap-8 md:grid-cols-[minmax(0,2fr),minmax(0,1.5fr)]">
                                <div>
                                    <FileUpload
                                        onFileSelect={handleFileSelect}
                                        isLoading={isUploading}
                                        maxFileSizeBytes={MAX_FILE_SIZE_BYTES}
                                    />

                                    {isUploading && (
                                        <div className="mt-6 space-y-3">
                                            {uploadProgress ? (
                                                <>
                                                    <div className="h-3 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                                                        <div
                                                            className={`h-full bg-blue-500 transition-all duration-300 ${
                                                                uploadProgress.phase === 'processing' ? 'animate-pulse' : ''
                                                            }`}
                                                            style={{ width: `${uploadProgress.pct}%` }}
                                                        />
                                                    </div>
                                                    <p className="text-center text-sm text-blue-600 dark:text-blue-400">
                                                        {uploadProgress.label}
                                                    </p>
                                                </>
                                            ) : (
                                                <div className="flex items-center justify-center gap-3 text-blue-600 dark:text-blue-400">
                                                    <Loader2 className="w-5 h-5 animate-spin" />
                                                    <span>Preparing upload...</span>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {error && (
                                        <div className="mt-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
                                            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                                            <div>
                                                <p className="font-semibold">Upload failed</p>
                                                <p className="mt-1">{error}</p>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50/80 p-4 text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-900/60 dark:text-gray-400">
                                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-500">
                                        Artifact requirements
                                    </h3>
                                    <ul className="space-y-1.5">
                                        <li>
                                            Drop your audit artifact — any file type can be uploaded.
                                        </li>
                                        <li>
                                            Full verification is supported for{" "}
                                            <span className="font-mono">.lm3z</span>,{" "}
                                            <span className="font-mono">.rim0</span>,{" "}
                                            <span className="font-mono">.rim95</span>{" "}
                                            artifacts.
                                        </li>
                                        <li>
                                            Other file types will receive limited analysis (hash, entropy, basic structure)
                                            but still produce a structured report.
                                        </li>
                                        <li>
                                            Maximum file size: {(MAX_FILE_SIZE_BYTES / 1024 / 1024 / 1024).toFixed(0)} GB
                                        </li>
                                    </ul>
                                    <h3 className="mt-4 mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-500">
                                        What you get
                                    </h3>
                                    <ul className="space-y-1.5">
                                        <li>Integrity score (0-100) from RIM-OS v2</li>
                                        <li>Risk classification with anomaly summary</li>
                                        <li>Optional PDF, HTML, and SVG report artifacts</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-8">
                        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 space-y-6">
                            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                                <div>
                                    <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                                        Audit Analysis
                                    </h2>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                        Deterministic weight integrity audit for your uploaded artifact.
                                    </p>
                                </div>
                                <div className="flex flex-col items-start md:items-end gap-2">
                                    <div className="flex items-center gap-3">
                                        <div className="text-right">
                                            <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-500">
                                                File
                                            </p>
                                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate max-w-xs">
                                                {uploadData.fileInfo.name}
                                            </p>
                                        </div>
                                        <div className="h-8 w-px bg-gray-200 dark:bg-gray-700" />
                                        <div className="text-right">
                                            <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-500">
                                                Size
                                            </p>
                                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                                                {(uploadData.fileInfo.size / 1024 / 1024).toFixed(2)} MB
                                            </p>
                                        </div>
                                    </div>
                                    <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-50/80 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                                        <ShieldCheck className="w-3 h-3" />
                                        <span>RIM-OS v2 canonical engine</span>
                                    </div>
                                </div>
                            </div>

                            <KPIDisplay
                                kpis={uploadData.kpis}
                                verification={uploadData.verification}
                                fileHash={uploadData.fileHash}
                                metadata={uploadData.metadata}
                            />

                            <div className="mt-6 flex flex-wrap gap-4">
                                <Link
                                    href={`/report/${uploadData.uploadId}`}
                                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors"
                                >
                                    <FileText className="w-4 h-4" />
                                    View Audit Report
                                </Link>
                                <a
                                    href={`${API_URL}/api/report/${uploadData.uploadId}/pdf`}
                                    download={`pass97_report_${uploadData.uploadId}.pdf`}
                                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                                >
                                    <Download className="w-4 h-4" />
                                    Download PDF Report
                                </a>
                                <a
                                    href={`${API_URL}/api/report/${uploadData.uploadId}/svg`}
                                    download={`penrose_${uploadData.uploadId}.svg`}
                                    className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
                                >
                                    <FileImage className="w-4 h-4" />
                                    Download Penrose SVG
                                </a>
                            </div>
                        </div>

                        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
                            <MintFlow uploadData={uploadData} />
                        </div>

                        <div className="text-center">
                            <button
                                onClick={() => {
                                    setUploadData(null);
                                    setError(null);
                                }}
                                className="px-6 py-3 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
                            >
                                Upload Another File
                            </button>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
