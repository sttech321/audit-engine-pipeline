'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import axios from 'axios';
import {
    ArrowLeft,
    Download,
    FileCode2,
    FileImage,
    Loader2,
    ShieldCheck,
    TriangleAlert,
    CheckCircle2,
    XCircle,
    Fingerprint,
    CalendarClock,
    Scale,
    ListChecks,
    BadgeCheck,
} from 'lucide-react';
import type { ExtendedAuditResult } from '@shared/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const formatTimestamp = (timestamp: string) => {
    if (!timestamp) return 'Not available';

    const numeric = Number(timestamp);
    const parsed = Number.isNaN(numeric)
        ? new Date(timestamp)
        : new Date(numeric * 1000);

    return Number.isNaN(parsed.getTime())
        ? timestamp
        : parsed.toLocaleString();
};

const formatMetricValue = (value: string | number) => typeof value === 'number' ? value.toFixed(2) : value;

const getVerificationTone = (status: string) => {
    const normalized = status.toLowerCase();
    if (normalized.includes('verified') && !normalized.includes('failed')) {
        if (normalized.includes('warning')) {
            return {
                badge: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900',
                panel: 'border-amber-200 bg-amber-50/80 dark:border-amber-900 dark:bg-amber-950/20',
                icon: <ShieldCheck className="w-8 h-8 text-amber-600 dark:text-amber-400" />,
            };
        }
        return {
            badge: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900',
            panel: 'border-emerald-200 bg-emerald-50/80 dark:border-emerald-900 dark:bg-emerald-950/20',
            icon: <BadgeCheck className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />,
        };
    }

    return {
        badge: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900',
        panel: 'border-red-200 bg-red-50/80 dark:border-red-900 dark:bg-red-950/20',
        icon: <TriangleAlert className="w-8 h-8 text-red-600 dark:text-red-400" />,
    };
};

const getCheckState = (check: string) => {
    const normalized = check.toLowerCase();
    const failed = /invalid|failed|error|rejected|mismatch/.test(normalized);
    return failed
        ? {
            label: 'Fail',
            icon: <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />,
            badge: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900',
        }
        : {
            label: 'Pass',
            icon: <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />,
            badge: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900',
        };
};

const parseCheck = (check: string) => {
    const [name, ...detailParts] = check.split(':');
    const details = detailParts.join(':').trim();
    return {
        name: name.trim(),
        details: details || 'No additional detail provided.',
    };
};

const Section = ({
    title,
    description,
    children,
}: {
    title: string;
    description?: string;
    children: React.ReactNode;
}) => (
    <section className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
        <div className="mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{title}</h2>
            {description && (
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{description}</p>
            )}
        </div>
        {children}
    </section>
);

export default function ReportPage() {
    const params = useParams<{ uploadId: string }>();
    const uploadId = params.uploadId;
    const [report, setReport] = useState<ExtendedAuditResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        let active = true;

        const loadReport = async () => {
            try {
                const response = await axios.get<ExtendedAuditResult>(`${API_URL}/api/report/${uploadId}/extended`);
                if (active) {
                    setReport(response.data);
                }
            } catch (err: unknown) {
                if (active) {
                    const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
                    setError(typeof detail === 'string' ? detail : err instanceof Error ? err.message : 'Failed to load report');
                }
            } finally {
                if (active) {
                    setIsLoading(false);
                }
            }
        };

        loadReport();
        return () => {
            active = false;
        };
    }, [uploadId]);

    if (isLoading) {
        return (
            <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#e0f2fe,_#f8fafc_55%)] dark:bg-gradient-to-br dark:from-gray-900 dark:to-gray-800">
                <div className="max-w-6xl mx-auto px-4 py-24 flex items-center justify-center gap-3 text-sky-700 dark:text-sky-400">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Loading audit report...</span>
                </div>
            </div>
        );
    }

    if (error || !report) {
        return (
            <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#e0f2fe,_#f8fafc_55%)] dark:bg-gradient-to-br dark:from-gray-900 dark:to-gray-800">
                <div className="max-w-6xl mx-auto px-4 py-12">
                    <Link href="/upload" className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100">
                        <ArrowLeft className="w-4 h-4" />
                        Back to Upload
                    </Link>
                    <div className="mt-8 rounded-2xl border border-red-200 bg-white p-8 shadow-xl dark:border-red-900 dark:bg-gray-800">
                        <div className="flex items-start gap-3 text-red-700 dark:text-red-300">
                            <TriangleAlert className="w-5 h-5 mt-0.5 shrink-0" />
                            <div>
                                <h1 className="text-xl font-semibold">Report unavailable</h1>
                                <p className="mt-2 text-sm">{error || 'Audit report not found.'}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    const verificationTone = getVerificationTone(report.verification.status);
    const checkCount = report.verification.checks.length;
    const signatureCheck = report.verification.checks.find((check) => /signature/i.test(check));
    const signatureStatus = signatureCheck
        ? getCheckState(signatureCheck).label
        : 'Not available';

    return (
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#e0f2fe,_#f8fafc_55%)] dark:bg-gradient-to-br dark:from-gray-900 dark:to-gray-800">
            <header className="border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between gap-4">
                    <Link href="/upload" className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100">
                        <ArrowLeft className="w-4 h-4" />
                        Back to Upload
                    </Link>
                    <div className="text-right">
                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500 dark:text-gray-500">Report Header</p>
                        <p className="font-mono text-sm text-gray-700 dark:text-gray-300">{uploadId}</p>
                    </div>
                </div>
            </header>

            <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
                <section className="bg-white/90 dark:bg-gray-800 rounded-3xl shadow-2xl border border-gray-200 dark:border-gray-700 p-8">
                    <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                        <div>
                            <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-sky-700 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-300">
                                <ShieldCheck className="w-3 h-3" />
                                Professional audit dashboard
                            </div>
                            <h1 className="mt-4 text-3xl md:text-4xl font-bold text-gray-900 dark:text-gray-100">
                                Audit Report
                            </h1>
                            <p className="mt-3 max-w-2xl text-sm md:text-base text-gray-600 dark:text-gray-400">
                                This page summarizes the verification result, security checks, and audit details for the selected artifact.
                            </p>
                        </div>

                        <div className="flex flex-wrap gap-3">
                            <a
                                href={`${API_URL}/api/report/${uploadId}/pdf`}
                                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                            >
                                <Download className="w-4 h-4" />
                                Download PDF
                            </a>
                            <a
                                href={`${API_URL}/api/report/${uploadId}/html`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
                            >
                                <FileCode2 className="w-4 h-4" />
                                Open HTML Report
                            </a>
                            <a
                                href={`${API_URL}/api/report/${uploadId}/svg`}
                                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white transition-colors"
                            >
                                <FileImage className="w-4 h-4" />
                                Download SVG
                            </a>
                        </div>
                    </div>
                </section>

                <section className={`rounded-3xl border p-8 shadow-xl ${verificationTone.panel}`}>
                    <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
                        <div className="flex items-start gap-4">
                            <div className="mt-1">{verificationTone.icon}</div>
                            <div>
                                <p className="text-xs uppercase tracking-[0.2em] text-gray-500 dark:text-gray-500">
                                    Verification Result
                                </p>
                                <h2 className="mt-2 text-2xl md:text-3xl font-bold text-gray-900 dark:text-gray-100">
                                    {report.verification.status}
                                </h2>
                                <div className={`mt-3 inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium ${verificationTone.badge}`}>
                                    {report.verification.status}
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 lg:min-w-[360px]">
                            <div className="rounded-2xl bg-white/80 dark:bg-gray-900/40 border border-white/70 dark:border-gray-700 p-4">
                                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-500">Confidence Score</p>
                                <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-gray-100">{report.verification.confidence}%</p>
                            </div>
                            <div className="rounded-2xl bg-white/80 dark:bg-gray-900/40 border border-white/70 dark:border-gray-700 p-4">
                                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-500">Verification Time</p>
                                <p className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">{formatTimestamp(report.verification.timestamp)}</p>
                            </div>
                        </div>
                    </div>
                </section>

                <div className="grid gap-8 lg:grid-cols-[minmax(0,1.15fr),minmax(0,0.85fr)]">
                    <div className="space-y-8">
                        <Section
                            title="File Information"
                            description="Core identifiers from the current audit record."
                        >
                            <div className="grid gap-4 md:grid-cols-2">
                                <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5">
                                    <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                                        <Fingerprint className="w-4 h-4" />
                                        <span className="text-xs uppercase tracking-wide">Report ID</span>
                                    </div>
                                    <p className="mt-3 break-all font-mono text-sm text-gray-800 dark:text-gray-200">{uploadId}</p>
                                </div>
                                <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5">
                                    <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                                        <CalendarClock className="w-4 h-4" />
                                        <span className="text-xs uppercase tracking-wide">Verification Date</span>
                                    </div>
                                    <p className="mt-3 text-sm font-medium text-gray-800 dark:text-gray-200">{formatTimestamp(report.verification.timestamp)}</p>
                                </div>
                                <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5 md:col-span-2">
                                    <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                                        <Fingerprint className="w-4 h-4" />
                                        <span className="text-xs uppercase tracking-wide">File Hash</span>
                                    </div>
                                    <p className="mt-3 break-all font-mono text-sm leading-6 text-gray-800 dark:text-gray-200">
                                        {report.file_hash}
                                    </p>
                                </div>
                            </div>
                        </Section>

                        <Section
                            title="Security Checks"
                            description="Structured results for each verification stage."
                        >
                            <div className="overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-700">
                                <div className="grid grid-cols-[minmax(0,1.3fr),120px,minmax(0,1.4fr)] bg-gray-50 dark:bg-gray-900/60 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                                    <div>Check Name</div>
                                    <div>Status</div>
                                    <div>Details</div>
                                </div>
                                <div className="divide-y divide-gray-200 dark:divide-gray-700">
                                    {report.verification.checks.map((check, index) => {
                                        const parsed = parseCheck(check);
                                        const state = getCheckState(check);
                                        return (
                                            <div key={`${check}-${index}`} className="grid grid-cols-1 gap-3 px-4 py-4 md:grid-cols-[minmax(0,1.3fr),120px,minmax(0,1.4fr)] md:items-center">
                                                <div className="font-medium text-gray-900 dark:text-gray-100">{parsed.name}</div>
                                                <div>
                                                    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${state.badge}`}>
                                                        {state.icon}
                                                        {state.label}
                                                    </span>
                                                </div>
                                                <div className="text-sm text-gray-600 dark:text-gray-400">{parsed.details}</div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </Section>

                        <Section
                            title="Audit Details"
                            description="Supporting compliance and ledger data from the extended audit result."
                        >
                            <div className="space-y-6">
                                <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5">
                                    <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                                        <Scale className="w-4 h-4" />
                                        <span className="text-xs uppercase tracking-wide">EU AI Act Mapping</span>
                                    </div>
                                    <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">{report.eu_ai_act.assessment}</p>
                                    <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">
                                        Category: {report.eu_ai_act.category} | Reference: {report.eu_ai_act.article_reference}
                                    </p>
                                </div>

                                <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5">
                                    <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                                        <ListChecks className="w-4 h-4" />
                                        <span className="text-xs uppercase tracking-wide">Legal Scope</span>
                                    </div>
                                    <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">{report.legal_disclosures.weight_space_scope}</p>
                                </div>

                                {report.ledger && (
                                    <div className="grid gap-4 md:grid-cols-2">
                                        <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5">
                                            <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Ledger Entry Hash</p>
                                            <p className="mt-3 break-all font-mono text-sm text-gray-800 dark:text-gray-200">{report.ledger.entry_hash}</p>
                                        </div>
                                        <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5">
                                            <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Next State Hash</p>
                                            <p className="mt-3 break-all font-mono text-sm text-gray-800 dark:text-gray-200">{report.ledger.next_state_hash || 'Not available'}</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </Section>
                    </div>

                    <div className="space-y-8">
                        <Section
                            title="KPI / Metrics"
                            description="Quick summary metrics for clients and reviewers."
                        >
                            <div className="grid gap-4 sm:grid-cols-2">
                                <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5">
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Confidence</p>
                                    <p className="mt-3 text-3xl font-bold text-gray-900 dark:text-gray-100">{report.verification.confidence}%</p>
                                </div>
                                <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5">
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Checks Completed</p>
                                    <p className="mt-3 text-3xl font-bold text-gray-900 dark:text-gray-100">{checkCount}</p>
                                </div>
                                <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5 sm:col-span-2">
                                    <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Signature Verification</p>
                                    <p className="mt-3 text-2xl font-bold text-gray-900 dark:text-gray-100">{signatureStatus}</p>
                                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                        {signatureCheck || 'No signature-specific check was included in the current report payload.'}
                                    </p>
                                </div>
                            </div>
                        </Section>

                        <Section
                            title="Verification Metrics"
                            description="Current KPI values returned by the audit pipeline."
                        >
                            <div className="space-y-4">
                                {report.kpis.map((kpi) => (
                                    <div key={kpi.id} className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 p-5">
                                        <div className="flex items-start justify-between gap-3">
                                            <div>
                                                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{kpi.label}</p>
                                                {kpi.description && (
                                                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{kpi.description}</p>
                                                )}
                                            </div>
                                            <span className="rounded-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">
                                                {kpi.status}
                                            </span>
                                        </div>
                                        <p className="mt-4 text-3xl font-bold text-gray-900 dark:text-gray-100">{formatMetricValue(kpi.value)}</p>
                                    </div>
                                ))}
                            </div>
                        </Section>

                        <Section
                            title="Download Actions"
                            description="Open or download the available report artifacts."
                        >
                            <div className="space-y-3">
                                <a
                                    href={`${API_URL}/api/report/${uploadId}/pdf`}
                                    className="flex items-center justify-between rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 px-4 py-4 hover:border-blue-300 dark:hover:border-blue-700 transition-colors"
                                >
                                    <span className="font-medium text-gray-900 dark:text-gray-100">PDF audit report</span>
                                    <Download className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                </a>
                                <a
                                    href={`${API_URL}/api/report/${uploadId}/html`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center justify-between rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 px-4 py-4 hover:border-emerald-300 dark:hover:border-emerald-700 transition-colors"
                                >
                                    <span className="font-medium text-gray-900 dark:text-gray-100">HTML report view</span>
                                    <FileCode2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                                </a>
                                <a
                                    href={`${API_URL}/api/report/${uploadId}/svg`}
                                    className="flex items-center justify-between rounded-2xl border border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 px-4 py-4 hover:border-purple-300 dark:hover:border-purple-700 transition-colors"
                                >
                                    <span className="font-medium text-gray-900 dark:text-gray-100">Penrose SVG artifact</span>
                                    <FileImage className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                                </a>
                            </div>
                        </Section>
                    </div>
                </div>
            </main>
        </div>
    );
}
