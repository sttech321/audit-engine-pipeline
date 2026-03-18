"use client";

import { useState, useCallback } from "react";
import { FileUpload } from "@/components/FileUpload";
import { KPIDisplay } from "@/components/KPIDisplay";
import { MintFlow } from "@/components/MintFlow";
import {
  ArrowLeft,
  Loader2,
  Download,
  FileImage,
  ShieldCheck,
  AlertTriangle,
  FileText,
  Shield,
  MapPinned,
  GitBranch,
} from "lucide-react";
import Link from "next/link";
import axios from "axios";
import type {
  KPI,
  UploadMetadata,
  UploadResponse,
  VerificationStatus,
} from "@shared/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const BASE = `${API_URL}/api`;
const MAX_FILE_SIZE_BYTES = Number(
  process.env.NEXT_PUBLIC_MAX_FILE_SIZE_BYTES || 10 * 1024 * 1024 * 1024,
);

const CHUNK_THRESHOLD = 100 * 1024 * 1024;
const CHUNK_SIZE = 20 * 1024 * 1024;
const CONCURRENCY = 8;
const CHUNK_RETRY_ATTEMPTS = 3;
const CHUNK_RETRY_DELAY_MS = 1000;

interface UploadProgress {
  phase: "uploading" | "processing";
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
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(
    null,
  );

  const extractErrorMessage = (err: unknown): string => {
    const detail = axios.isAxiosError(err)
      ? err.response?.data?.detail
      : undefined;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "error" in detail) {
      const error = detail.error;
      if (
        error &&
        typeof error === "object" &&
        "message" in error &&
        typeof error.message === "string"
      )
        return error.message;
      if (
        error &&
        typeof error === "object" &&
        "code" in error &&
        typeof error.code === "string"
      )
        return error.code;
    }
    return err instanceof Error ? err.message : "Failed to upload file";
  };

  const mapChunkedToUploadResponse = (r: {
    upload_id: string;
    file_info: { name: string; size: number; type?: string };
    kpis: KPI[];
    verification: VerificationStatus;
    file_hash: string;
    metadata: UploadMetadata;
    artifact_block?: import("@shared/types").ArtifactBlock | null;
  }): UploadResponse => ({
    uploadId: r.upload_id,
    fileInfo: {
      name: r.file_info.name,
      size: r.file_info.size,
      type: r.file_info.type ?? "application/octet-stream",
    },
    kpis: r.kpis,
    verification: r.verification,
    fileHash: r.file_hash,
    metadata: r.metadata,
    artifactBlock: r.artifact_block ?? null,
  });

  const uploadChunked = useCallback(async (file: File) => {
    const chunkSize = CHUNK_SIZE;
    const totalChunks = Math.ceil(file.size / chunkSize);
    if (totalChunks > 1000)
      throw new Error("File too large. Try increasing chunk size.");

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
        form.append("file", blob, file.name);
        try {
          await axios.put(
            `${BASE}/upload/chunked/${upload_id}/chunk/${index}`,
            form,
            {
              maxBodyLength: Infinity,
              timeout: 0,
            },
          );
          completedCount++;
          const bytesLoaded = Math.min(completedCount * chunkSize, file.size);
          setUploadProgress({
            phase: "uploading",
            pct: (100 * completedCount) / totalChunks,
            label: `Uploading: ${formatMb(bytesLoaded)} MB of ${formatMb(file.size)} MB`,
            bytesLoaded,
            bytesTotal: file.size,
            chunksUploaded: completedCount,
            chunksTotal: totalChunks,
          });
          return;
        } catch (err) {
          lastErr = err;
          if (attempt < CHUNK_RETRY_ATTEMPTS - 1) {
            await new Promise((r) =>
              setTimeout(r, CHUNK_RETRY_DELAY_MS * (attempt + 1)),
            );
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
      phase: "processing",
      pct: 0,
      label: "Upload complete. Resolving spectral structure…",
      bytesLoaded: file.size,
      bytesTotal: file.size,
      chunksUploaded: totalChunks,
      chunksTotal: totalChunks,
    });

    const completeRes = await axios.post(
      `${BASE}/upload/chunked/${upload_id}/complete`,
      null,
      {
        validateStatus: (s) => s === 200 || s === 202,
      },
    );

    if (completeRes.status === 200 && completeRes.data?.file_info) {
      return mapChunkedToUploadResponse(completeRes.data);
    }

    const pollInterval = 1500;
    while (true) {
      const statusRes = await axios.get(
        `${BASE}/upload/chunked/${upload_id}/status`,
      );
      const { status, processing_pct, result, error } = statusRes.data;
      setUploadProgress({
        phase: "processing",
        pct: processing_pct ?? 0,
        label: `Resolving spectral structure… ${(processing_pct ?? 0).toFixed(0)}%`,
        bytesLoaded: file.size,
        bytesTotal: file.size,
        chunksUploaded: totalChunks,
        chunksTotal: totalChunks,
      });
      if (status === "completed" && result)
        return mapChunkedToUploadResponse(result);
      if (status === "failed") throw new Error(error || "Processing failed");
      await new Promise((r) => setTimeout(r, pollInterval));
    }
  }, []);

  const uploadSingle = useCallback(async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await axios.post<UploadResponse>(
      `${BASE}/upload`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
        timeout: 0,
        onUploadProgress: (e) => {
          const pct = e.total ? Math.round((100 * e.loaded) / e.total) : 0;
          const loadedMb = (e.loaded / 1024 / 1024).toFixed(1);
          const totalMb = e.total ? (e.total / 1024 / 1024).toFixed(1) : "?";
          const isUploadComplete = e.total && e.loaded >= e.total;
          setUploadProgress({
            phase: isUploadComplete ? "processing" : "uploading",
            pct,
            label: isUploadComplete
              ? "Upload complete. Resolving spectral structure…"
              : `Uploading: ${loadedMb} MB of ${totalMb} MB`,
            bytesLoaded: e.loaded,
            bytesTotal: e.total ?? undefined,
          });
        },
      },
    );
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
        phase: "uploading",
        pct: 0,
        label: `Uploading: 0 MB of ${sizeMb} MB`,
        bytesLoaded: 0,
        bytesTotal: file.size,
      });
      const result = useChunked
        ? await uploadChunked(file)
        : await uploadSingle(file);
      setUploadData(result);
    } catch (err: unknown) {
      setError(extractErrorMessage(err));
      console.error("Upload error:", err);
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#08111f] text-white">
      {/* Background */}
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_50%_at_50%_0%,rgba(251,191,36,0.12),transparent),radial-gradient(ellipse_50%_50%_at_80%_30%,rgba(56,189,248,0.10),transparent)]" />
      </div>

      {/* Header */}
      <header className="relative z-50 border-b border-white/8 glass">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <Link
              href="/"
              className="flex items-center gap-2 text-slate-400 hover:text-amber-200 transition-colors text-sm"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Home
            </Link>
            <div className="flex items-center gap-3">
              <Shield className="h-7 w-7 text-amber-300" />
              <h1 className="text-lg font-semibold tracking-[0.16em] text-slate-100 uppercase">
                RIMOS
              </h1>
            </div>
            <div className="w-28" />
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        {!uploadData ? (
          <div className="mx-auto max-w-3xl">
            <div className="rounded-[2rem] glass p-10 shadow-2xl shadow-black/40">
              {/* Title */}
              <div className="mb-8">
                <h2 className="text-4xl font-semibold text-white">
                  Upload Artifact
                </h2>
                <p className="mt-3 text-base text-slate-400 leading-7">
                  RIMOS maps your artifact into a mathematical landscape —
                  revealing its spectral structure, geometric position, and
                  verification summary.
                </p>
                <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-400/8 px-4 py-2 text-xs font-semibold text-emerald-300 tracking-wide">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Deterministic RIMOS mapping pipeline
                </div>
              </div>

              <div className="grid gap-8 md:grid-cols-[minmax(0,2fr),minmax(0,1.5fr)]">
                {/* Drop zone */}
                <div>
                  <FileUpload
                    onFileSelect={handleFileSelect}
                    isLoading={isUploading}
                    maxFileSizeBytes={MAX_FILE_SIZE_BYTES}
                  />

                  {/* Progress */}
                  {isUploading && (
                    <div className="mt-6 space-y-3">
                      {uploadProgress ? (
                        <>
                          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                            <div
                              className={`h-full progress-gradient transition-all duration-300 ${uploadProgress.phase === "processing" ? "animate-pulse" : ""}`}
                              style={{ width: `${uploadProgress.pct}%` }}
                            />
                          </div>
                          <p className="text-center text-sm text-amber-200/80">
                            {uploadProgress.label}
                          </p>
                        </>
                      ) : (
                        <div className="flex items-center justify-center gap-3 text-amber-300">
                          <Loader2 className="w-5 h-5 animate-spin" />
                          <span className="text-sm">Preparing artifact…</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Error */}
                  {error && (
                    <div className="mt-5 flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-4 text-sm text-red-300">
                      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-red-400" />
                      <div>
                        <p className="font-semibold text-red-200">
                          Artifact upload failed
                        </p>
                        <p className="mt-1 text-red-300/80">{error}</p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Guidance sidebar */}
                <div className="rounded-2xl border border-white/8 bg-slate-950/50 p-5 text-sm text-slate-400">
                  <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Artifact guidance
                  </h3>
                  <ul className="space-y-2">
                    <li>Upload any artifact to enter the analysis flow.</li>
                    <li>
                      Full audit for{" "}
                      <span className="font-mono text-amber-200">.lm3z</span>{" "}
                      <span className="font-mono text-amber-200">.rim0</span>{" "}
                      <span className="font-mono text-amber-200">.rim95</span>{" "}
                      <span className="font-mono text-amber-200">.safetensors</span>{" "}
                      <span className="font-mono text-amber-200">.bin</span>{" "}
                      <span className="font-mono text-amber-200">.gguf</span>{" "}
                      <span className="font-mono text-amber-200">.pt</span>{" "}
                      <span className="font-mono text-amber-200">.pth</span>{" "}
                      <span className="font-mono text-amber-200">.ckpt</span>{" "}
                      <span className="font-mono text-amber-200">.onnx</span>.
                    </li>
                    <li>Other types receive structural analysis.</li>
                    <li>
                      Max size:{" "}
                      {(MAX_FILE_SIZE_BYTES / 1024 / 1024 / 1024).toFixed(0)} GB
                    </li>
                  </ul>
                  <h3 className="mt-5 mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                    What you receive
                  </h3>
                  <ul className="space-y-2">
                    <li>Deterministic verification summary & fingerprint</li>
                    <li>Spectral, separability & risk metrics</li>
                    <li>PDF, HTML, and Penrose SVG report artifacts</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Results panel */}
            <div className="rounded-[2rem] glass p-10 shadow-2xl shadow-black/40 space-y-8">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-3xl font-semibold text-white">
                    Artifact Map Result
                  </h2>
                  <p className="text-sm text-slate-400 mt-1">
                    Your artifact has been resolved into a deterministic
                    position in the RIMOS mathematical landscape.
                  </p>
                </div>
                <div className="flex flex-col items-start md:items-end gap-2">
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-xs uppercase tracking-wide text-slate-500">
                        File
                      </p>
                      <p className="text-sm font-semibold text-slate-200 truncate max-w-xs">
                        {uploadData.fileInfo.name}
                      </p>
                    </div>
                    <div className="h-8 w-px bg-white/10" />
                    <div className="text-right">
                      <p className="text-xs uppercase tracking-wide text-slate-500">
                        Size
                      </p>
                      <p className="text-sm font-semibold text-slate-200">
                        {(uploadData.fileInfo.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-400/8 px-3 py-1.5 text-xs font-semibold text-emerald-300">
                    <ShieldCheck className="w-3 h-3" />
                    RIMOS deterministic engine
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-sky-400/15 bg-sky-400/6 p-6">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  Position Summary
                </p>
                <p className="mt-3 text-sm leading-7 text-slate-300">
                  The artifact is treated as an independent point on the Penrose
                  map. The metrics below describe the condition and structure of
                  that point; they do not create the point itself.
                </p>
                <p className="mt-3 text-sm leading-7 text-slate-400">
                  Open the full map report to view tau coordinates, manifold
                  hash, tile hash, anchor weighting, and the Penrose
                  visualization for this position.
                </p>
              </div>

              {uploadData.artifactBlock && (
                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-6 backdrop-blur">
                    <div className="flex items-center gap-2 mb-3">
                      <MapPinned className="w-4 h-4 text-slate-500" />
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                        Map Snapshot
                      </p>
                    </div>
                    <p className="text-sm leading-7 text-slate-400">
                      A compact view of the coordinates already generated for
                      this artifact position.
                    </p>

                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                      {uploadData.artifactBlock.tau_vectors.map((value, index) => (
                        <div
                          key={`tau-summary-${index}`}
                          className="rounded-xl border border-sky-400/15 bg-sky-400/6 px-4 py-3"
                        >
                          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                            τ{index + 1}
                          </p>
                          <p className="mt-2 font-mono text-sm font-semibold text-sky-300">
                            {value.toFixed(4)}
                          </p>
                        </div>
                      ))}
                    </div>

                    <div className="mt-4 space-y-3">
                      <div className="rounded-xl border border-white/8 bg-slate-900/60 p-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          Manifold Hash
                        </p>
                        <p className="mt-2 break-all font-mono text-xs text-amber-200/80">
                          {uploadData.artifactBlock.manifold_hash}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/8 bg-slate-900/60 p-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          Tile Hash
                        </p>
                        <p className="mt-2 break-all font-mono text-xs text-amber-200/80">
                          {uploadData.artifactBlock.tile_hash}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-6 backdrop-blur">
                    <div className="flex items-center gap-2 mb-3">
                      <GitBranch className="w-4 h-4 text-slate-500" />
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                        Blockchain Record
                      </p>
                    </div>
                    <p className="text-sm leading-7 text-slate-400">
                      This mapped artifact position has been written into the
                      internal blockchain as a new chain record.
                    </p>

                    <div className="mt-5 grid gap-4 sm:grid-cols-2">
                      <div className="rounded-xl border border-white/8 bg-slate-900/60 p-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          Block Index
                        </p>
                        <p className="mt-2 text-2xl font-semibold text-sky-300">
                          {uploadData.artifactBlock.index}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/8 bg-slate-900/60 p-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          Chain Height
                        </p>
                        <p className="mt-2 text-2xl font-semibold text-sky-300">
                          {uploadData.artifactBlock.index + 1}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/8 bg-slate-900/60 p-4 sm:col-span-2">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          Timestamp
                        </p>
                        <p className="mt-2 text-sm font-medium text-slate-300">
                          {uploadData.artifactBlock.timestamp}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/8 bg-slate-900/60 p-4 sm:col-span-2">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          Artifact Hash
                        </p>
                        <p className="mt-2 break-all font-mono text-xs text-amber-200/80">
                          {uploadData.artifactBlock.artifact_hash}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/8 bg-slate-900/60 p-4 sm:col-span-2">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          Block Hash
                        </p>
                        <p className="mt-2 break-all font-mono text-xs text-amber-200/80">
                          {uploadData.artifactBlock.block_hash}
                        </p>
                      </div>
                      <div className="rounded-xl border border-white/8 bg-slate-900/60 p-4 sm:col-span-2">
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                          Previous Block
                        </p>
                        <p className="mt-2 break-all font-mono text-xs text-amber-200/80">
                          {uploadData.artifactBlock.prev_block_hash || "Genesis-linked origin"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <KPIDisplay
                kpis={uploadData.kpis}
                verification={uploadData.verification}
                fileHash={uploadData.fileHash}
                metadata={uploadData.metadata}
              />

              {/* Action buttons */}
              <div className="flex flex-wrap gap-3">
                <Link
                  href={`/report/${uploadData.uploadId}`}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl glass-amber text-amber-200 text-sm font-semibold transition hover:bg-amber-300/20"
                >
                  <FileText className="w-4 h-4" />
                  View Map Report
                </Link>
                <a
                  href={`${API_URL}/api/report/${uploadData.uploadId}/pdf`}
                  download={`RIMOS_report_${uploadData.uploadId}.pdf`}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl glass-sky text-sky-200 text-sm font-semibold transition hover:bg-sky-300/20"
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </a>
                <a
                  href={`${API_URL}/api/report/${uploadData.uploadId}/svg`}
                  download={`penrose_${uploadData.uploadId}.svg`}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl glass-violet text-violet-200 text-sm font-semibold transition hover:bg-violet-300/20"
                >
                  <FileImage className="w-4 h-4" />
                  Penrose SVG
                </a>
              </div>
            </div>

            {/* Mint flow */}
            <div className="rounded-[2rem] glass p-10 shadow-2xl shadow-black/40">
              <div className="mb-6">
                <h3 className="text-2xl font-semibold text-white">
                  Optional Provenance Certificate
                </h3>
                <p className="mt-2 text-sm leading-7 text-slate-400">
                  NFT minting is optional. It acts as a certificate for this
                  mapped artifact position and does not define the position
                  itself.
                </p>
              </div>
              {/* <MintFlow uploadData={uploadData} /> */}
            </div>

            <div className="text-center">
              <button
                onClick={() => {
                  setUploadData(null);
                  setError(null);
                }}
                className="px-6 py-3 rounded-xl border border-white/10 text-slate-400 hover:text-amber-200 hover:border-amber-300/30 transition-colors text-sm"
              >
                Upload Another Artifact
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
