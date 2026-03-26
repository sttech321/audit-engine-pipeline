"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import axios from "axios";
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
  Shield,
  MapPinned,
} from "lucide-react";
import type { ArtifactBlock, ExtendedAuditResult } from "@shared/types";
import BlockchainInfo from "@/components/BlockchainInfo";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ReportWithChain = ExtendedAuditResult & {
  artifact_block?: ArtifactBlock | null;
  chain_height?: number;
};

const formatTimestamp = (timestamp: string) => {
  if (!timestamp) return "Not available";
  const numeric = Number(timestamp);
  const parsed = Number.isNaN(numeric)
    ? new Date(timestamp)
    : new Date(numeric * 1000);
  return Number.isNaN(parsed.getTime()) ? timestamp : parsed.toLocaleString();
};

const formatMetricValue = (value: string | number) =>
  typeof value === "number" ? value.toFixed(2) : value;

const getVerificationTone = (status: string) => {
  const normalized = status.toLowerCase();
  if (normalized.includes("verified") && !normalized.includes("failed")) {
    if (normalized.includes("warning")) {
      return {
        border: "border-amber-400/30",
        bg: "bg-amber-400/8",
        iconColor: "text-amber-400",
        titleColor: "text-amber-300",
        badgeClass: "bg-amber-400/15 text-amber-300 border-amber-400/30",
        icon: <ShieldCheck className="w-8 h-8 text-amber-400" />,
      };
    }
    return {
      border: "border-emerald-400/30",
      bg: "bg-emerald-400/8",
      iconColor: "text-emerald-400",
      titleColor: "text-emerald-300",
      badgeClass: "bg-emerald-400/15 text-emerald-300 border-emerald-400/30",
      icon: <BadgeCheck className="w-8 h-8 text-emerald-400" />,
    };
  }
  return {
    border: "border-red-500/30",
    bg: "bg-red-500/8",
    iconColor: "text-red-400",
    titleColor: "text-red-300",
    badgeClass: "bg-red-500/15 text-red-300 border-red-500/30",
    icon: <TriangleAlert className="w-8 h-8 text-red-400" />,
  };
};

const getCheckState = (check: string) => {
  const failed = /invalid|failed|error|rejected|mismatch/i.test(check);
  return failed
    ? {
        label: "Fail",
        icon: <XCircle className="w-4 h-4 text-red-400" />,
        badge: "bg-red-500/15 text-red-300 border-red-500/30",
      }
    : {
        label: "Pass",
        icon: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
        badge: "bg-emerald-400/15 text-emerald-300 border-emerald-400/30",
      };
};

const parseCheck = (check: string) => {
  const [name, ...detailParts] = check.split(":");
  return {
    name: name.trim(),
    details: detailParts.join(":").trim() || "No additional detail provided.",
  };
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const formatJson = (value: unknown) => JSON.stringify(value, null, 2);

const ARTICLE_KEYS = [
  "Art_9_risk",
  "Art_10_data",
  "Art_11_docs",
  "Art_12_logging",
  "Art_13_transparency",
  "Art_14_oversight",
  "Art_15_robustness",
] as const;

type ArticleCard = {
  key: (typeof ARTICLE_KEYS)[number];
  title: string;
  summary: string;
};
const getArticleCards = (value: Record<string, unknown> | null) =>
  ARTICLE_KEYS.map((key) => {
    const block = value?.[key];
    if (!isRecord(block)) return null;
    return {
      key,
      title: String(block.article ?? key.replaceAll("_", " ")),
      summary: String(
        block.overall_assessment ??
          block.description ??
          block.data_quality_statement ??
          block.documentation_status ??
          block.transparency_status ??
          block.oversight_status ??
          block.robustness_status ??
          "Assessment available in attached report.",
      ),
    };
  }).filter((item): item is ArticleCard => item !== null);

const Section = ({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) => (
  <section className="rounded-[2rem] border border-white/8 bg-slate-950/60 p-8 backdrop-blur shadow-xl shadow-black/30">
    <div className="mb-6">
      <h2 className="text-xl font-semibold text-white">{title}</h2>
      {description && (
        <p className="mt-1.5 text-sm text-slate-400">{description}</p>
      )}
    </div>
    {children}
  </section>
);

/* ── Info tile used in multiple sections ── */
const InfoTile = ({
  label,
  icon: Icon,
  children,
  full,
}: {
  label: string;
  icon?: React.ElementType;
  children: React.ReactNode;
  full?: boolean;
}) => (
  <div
    className={`rounded-2xl border border-white/8 bg-slate-900/60 p-5 ${full ? "col-span-2" : ""}`}
  >
    <div className="flex items-center gap-2 mb-3">
      {Icon && <Icon className="w-4 h-4 text-slate-500" />}
      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {label}
      </span>
    </div>
    {children}
  </div>
);

export default function ReportPage() {
  const params = useParams<{ uploadId: string }>();
  const uploadId = params.uploadId;
  const [report, setReport] = useState<ReportWithChain | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEuPayloadOpen, setIsEuPayloadOpen] = useState(false);

  useEffect(() => {
    let active = true;
    const loadReport = async () => {
      try {
        const response = await axios.get<ReportWithChain>(
          `${API_URL}/api/report/${uploadId}/extended`,
        );
        if (active) setReport(response.data);
      } catch (err: unknown) {
        if (active) {
          const detail = axios.isAxiosError(err)
            ? err.response?.data?.detail
            : undefined;
          setError(
            typeof detail === "string"
              ? detail
              : err instanceof Error
                ? err.message
                : "Failed to load report",
          );
        }
      } finally {
        if (active) setIsLoading(false);
      }
    };
    loadReport();
    return () => {
      active = false;
    };
  }, [uploadId]);

  /* ── Loading state ── */
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#08111f] flex items-center justify-center">
        <div className="flex items-center gap-3 text-amber-300">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading audit report…</span>
        </div>
      </div>
    );
  }

  /* ── Error state ── */
  if (error || !report) {
    return (
      <div className="min-h-screen bg-[#08111f] text-white">
        <div className="max-w-6xl mx-auto px-4 py-12">
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 text-slate-400 hover:text-amber-200 transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Upload
          </Link>
          <div className="mt-8 rounded-[2rem] border border-red-500/30 bg-red-500/8 p-8 backdrop-blur">
            <div className="flex items-start gap-3 text-red-300">
              <TriangleAlert className="w-5 h-5 mt-0.5 shrink-0" />
              <div>
                <h1 className="text-xl font-semibold">Report unavailable</h1>
                <p className="mt-2 text-sm text-red-300/80">
                  {error || "Audit report not found."}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const tone = getVerificationTone(report.verification.status);
  const checkCount = report.verification.checks.length;
  const signatureCheck = report.verification.checks.find((c) =>
    /signature/i.test(c),
  );
  const signatureStatus = signatureCheck
    ? getCheckState(signatureCheck).label
    : "Not available";

  const kpiValueColor = (status: string) =>
    status === "excellent"
      ? "text-emerald-300"
      : status === "good"
        ? "text-sky-300"
        : status === "warning"
          ? "text-amber-300"
          : "text-slate-200";

  const kpiBadge = (status: string) =>
    status === "excellent"
      ? "bg-emerald-400/15 text-emerald-300 border-emerald-400/30"
      : status === "good"
        ? "bg-sky-400/15 text-sky-300 border-sky-400/30"
        : status === "warning"
          ? "bg-amber-400/15 text-amber-300 border-amber-400/30"
          : "bg-slate-700/40 text-slate-400 border-white/10";

  const euAiFull = isRecord(report.EU_AI_ACT_FULL) ? report.EU_AI_ACT_FULL : null;
  const euAiConformity = euAiFull && isRecord(euAiFull.conformity) ? euAiFull.conformity : null;
  const euAiMeta = euAiFull && isRecord(euAiFull.meta) ? euAiFull.meta : null;
  const euAiArticles = getArticleCards(euAiFull);
  const complianceStatus = String(
    euAiConformity?.compliance_status ?? "NOT_AVAILABLE",
  );
  const complianceBadge =
    complianceStatus === "PASS"
      ? "bg-emerald-400/15 text-emerald-300 border-emerald-400/30"
      : complianceStatus === "CONDITIONAL_PASS"
        ? "bg-amber-400/15 text-amber-300 border-amber-400/30"
        : "bg-red-500/15 text-red-300 border-red-500/30";

  const findKpi = (label: string) =>
    report.kpis.find((k) => k.label === label);

  const toNumber = (v: unknown): number | null => {
    if (typeof v === "number") return v;
    if (typeof v === "string") {
      const parsed = Number(v);
      return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
  };

  const auditScoreKpi = findKpi("Audit Score");
  const issuesFoundKpi = findKpi("Issues Found");
  const anomalyCount = toNumber(issuesFoundKpi?.value) ?? 0;
  const auditScore = toNumber(auditScoreKpi?.value) ?? 0;

  const rawEuCategory = String(report.eu_ai_act?.category ?? "");
  const riskLabel =
    rawEuCategory === "MINIMAL_RISK"
      ? "Minimal Risk"
      : rawEuCategory === "LIMITED_RISK"
        ? "Limited Risk"
        : "High Risk";

  const complianceStatusPretty =
    complianceStatus === "PASS"
      ? "Pass"
      : complianceStatus === "CONDITIONAL_PASS"
        ? "Conditional Pass"
        : complianceStatus === "FAIL"
          ? "Fail"
          : "Not available";

  const humanReviewNeeded =
    typeof euAiConformity?.human_review_needed === "boolean"
      ? euAiConformity.human_review_needed
      : report.verification.status.toLowerCase().includes("failed");

  const recommendationText =
    riskLabel === "Minimal Risk"
      ? "This artifact passed structural integrity checks with no anomalies detected. It is suitable for development/testing use."
      : riskLabel === "Limited Risk"
        ? `Minor irregularities were detected (${anomalyCount} anomaly${
            anomalyCount === 1 ? "" : "ies"
          }). Review is recommended before production use.`
        : `Critical integrity signals were detected (${anomalyCount} anomaly${
            anomalyCount === 1 ? "" : "ies"
          }). Manual review is required before any production use.`;

  const whatThisMeansText =
    riskLabel === "Minimal Risk"
      ? "The system found no critical irregularities in the artifact structure."
      : riskLabel === "Limited Risk"
        ? "The system found minor irregularities in the artifact structure. These are not critical, but should be reviewed if the artifact will be used in production."
        : "The system found critical integrity issues in the artifact structure. Do not use this artifact for production without human review.";

  const humanReviewGuidanceText = humanReviewNeeded
    ? "Human review is required based on the current thresholds. Consider re-uploading a different artifact or performing additional domain validation before production use."
    : "Manual review is not required based on current thresholds. However, review is recommended if the model will be used in production or in sensitive use cases.";

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#08111f] text-white">
      {/* Background */}
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_40%_at_50%_0%,rgba(251,191,36,0.10),transparent),radial-gradient(ellipse_50%_40%_at_80%_30%,rgba(56,189,248,0.08),transparent)]" />
      </div>

      {/* Header */}
      <header className="relative z-50 border-b border-white/8 glass">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between gap-4">
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 text-slate-400 hover:text-amber-200 transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Upload
          </Link>
          <div className="flex items-center gap-3">
            <Shield className="h-7 w-7 text-amber-300" />
            <span className="text-lg font-semibold tracking-[0.16em] text-slate-100 uppercase">
              RIMOS
            </span>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-600">
              Report ID
            </p>
            <p className="font-mono text-xs text-slate-400 truncate max-w-[200px]">
              {uploadId}
            </p>
          </div>
        </div>
      </header>

      <main className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
        {/* ── Executive Summary ── */}
        <Section
          title="Executive Summary"
          description="A human-readable overview of this artifact&apos;s deterministic audit results."
        >
          <div className="space-y-4">
            <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
              <p className="text-sm leading-7 text-slate-300">
                This file has been analyzed using the RIMOS audit system. The result
                below represents the artifact&apos;s deterministic structural mapping on the
                Penrose space.
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className={`rounded-xl border ${tone.border} ${tone.bg} p-4`}>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    Result
                  </p>
                  <p className="mt-2 text-sm font-semibold text-white">
                    {report.verification.status}
                  </p>
                </div>
                <div
                  className={`rounded-xl border p-4 ${
                    riskLabel === "Minimal Risk"
                      ? "border-emerald-400/25 bg-emerald-400/6"
                      : riskLabel === "Limited Risk"
                        ? "border-amber-400/25 bg-amber-400/6"
                        : "border-red-500/25 bg-red-500/6"
                  }`}
                >
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    Risk Level
                  </p>
                  <p
                    className={`mt-2 text-sm font-semibold ${
                      riskLabel === "Minimal Risk"
                        ? "text-emerald-300"
                        : riskLabel === "Limited Risk"
                          ? "text-amber-200"
                          : "text-red-300"
                    }`}
                  >
                    {riskLabel}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    {riskLabel === "Minimal Risk"
                      ? "This classification is based on low anomaly signals, stable deterministic structure, and no critical integrity flags."
                      : riskLabel === "Limited Risk"
                        ? `This classification is based on ${anomalyCount} anomaly signal${anomalyCount === 1 ? "" : "s"}, an audit score of ~${auditScore.toFixed(
                            0,
                          )}/100, and threshold-based integrity checks.`
                        : `This classification is based on ${anomalyCount} anomaly signal${anomalyCount === 1 ? "" : "s"}, an audit score of ~${auditScore.toFixed(
                            0,
                          )}/100, and threshold-based integrity checks requiring escalation.`}
                  </p>
                </div>
                <div className={`rounded-xl border ${tone.border} ${tone.bg} p-4`}>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    Confidence
                  </p>
                  <p className="mt-2 text-sm font-semibold text-slate-200">
                    {report.verification.confidence}%
                  </p>
                </div>
              </div>
            </div>

            <div
              className={`rounded-2xl border p-5 ${
                riskLabel === "Minimal Risk"
                  ? "border-emerald-400/15 bg-emerald-400/6"
                  : riskLabel === "Limited Risk"
                    ? "border-amber-400/15 bg-amber-400/6"
                    : "border-red-500/15 bg-red-500/6"
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                {riskLabel === "Minimal Risk" ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : riskLabel === "Limited Risk" ? (
                  <TriangleAlert className="w-4 h-4 text-amber-300" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-300" />
                )}
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  Recommendation
                </p>
              </div>
              <p className="text-sm text-slate-300 leading-7">
                {recommendationText}
              </p>
              <p className="mt-3 text-xs text-slate-500">
                Why this classification: The audit assesses deterministic structural integrity
                and anomaly signals across mapped chunks. Your confidence score is {report.verification.confidence}%;
                reliability is strongest for structural integrity checks.
              </p>
            </div>
          </div>
        </Section>

        {/* ── Hero / title panel ── */}
        <section className="rounded-[2rem] glass p-8 shadow-2xl shadow-black/40">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/30 bg-sky-400/8 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-sky-300">
                <ShieldCheck className="w-3.5 h-3.5" />
                Artifact map report
              </div>
              <h1 className="mt-5 text-4xl font-semibold text-white md:text-5xl">
                Artifact Map Report
              </h1>
              <p className="mt-3 max-w-2xl text-base text-slate-400">
                This artifact has been located as a deterministic point on the
                Penrose map. Coordinates, anchors, ledger continuity, and audit
                evidence are shown below.
              </p>
            </div>

            <div className="flex flex-wrap gap-3 shrink-0">
              <a
                href={`${API_URL}/api/report/${uploadId}/pdf`}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl glass-sky text-sky-200 text-sm font-semibold transition hover:bg-sky-300/20"
              >
                <Download className="w-4 h-4" />
                Download PDF
              </a>
              <a
                href={`${API_URL}/api/report/${uploadId}/html`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl glass-amber text-amber-200 text-sm font-semibold transition hover:bg-amber-300/20"
              >
                <FileCode2 className="w-4 h-4" />
                Open HTML
              </a>
              <a
                href={`${API_URL}/api/report/${uploadId}/svg`}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl glass-violet text-violet-200 text-sm font-semibold transition hover:bg-violet-300/20"
              >
                <FileImage className="w-4 h-4" />
                Penrose SVG
              </a>
            </div>
          </div>
        </section>

        {/* ── Verification result banner ── */}
        <section
          className={`rounded-[2rem] border p-8 backdrop-blur ${tone.border} ${tone.bg}`}
        >
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-4">
              <div className="mt-1">{tone.icon}</div>
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-slate-500">
                  Current Verification State
                </p>
                <h2 className={`mt-2 text-3xl font-bold ${tone.titleColor}`}>
                  {report.verification.status}
                </h2>
                <p className="mt-2 max-w-xl text-sm text-slate-400">
                  The artifact remains an independent point on the map. This
                  status describes the current verification outcome for that
                  position, not whether the position exists.
                </p>
                <p className="mt-2 max-w-xl text-sm text-slate-300">
                  <strong>What this means:</strong> {whatThisMeansText}
                </p>
                <p className="mt-2 max-w-xl rounded-xl border border-sky-400/20 bg-sky-400/6 p-3 text-sm text-slate-200 leading-6">
                  <strong>Decision-ready summary:</strong> {recommendationText}
                </p>
                <div
                  className={`mt-3 inline-flex items-center rounded-full border px-4 py-1.5 text-sm font-semibold ${tone.badgeClass}`}
                >
                  {report.verification.status}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 lg:min-w-[320px]">
              <div className="rounded-2xl border border-white/8 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Confidence Score
                </p>
                <p className={`mt-2 text-3xl font-bold ${tone.titleColor}`}>
                  {report.verification.confidence}%
                </p>
              </div>
              <div className="rounded-2xl border border-white/8 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Verified At
                </p>
                <p className="mt-2 text-sm font-medium text-slate-300">
                  {formatTimestamp(report.verification.timestamp)}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── Two-column layout ── */}
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1.15fr),minmax(0,0.85fr)]">
          {/* ── Left column ── */}
          <div className="space-y-8">
            <Section
              title="Artifact Map Position"
              description="The existing RIMOS pipeline exposes this artifact as a coordinate on the Penrose map."
            >
              {report.map_position ? (
                <div className="space-y-5">
                  <div className="rounded-2xl border border-sky-400/15 bg-sky-400/6 p-5">
                    <p className="text-sm leading-7 text-slate-300">
                      Artifact {"->"} mathematical pipeline {"->"} map position. The
                      values below are the coordinate output already generated by
                      the deterministic Godel {"->"} p-adic {"->"} NTT {"->"} KAG {"->"} Penrose
                      path.
                    </p>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <InfoTile label="Manifold Hash" icon={MapPinned} full>
                      <p className="break-all font-mono text-xs leading-6 text-amber-200/70 rounded-xl border border-amber-300/15 bg-amber-300/5 p-3">
                        {report.map_position.manifold_hash}
                      </p>
                    </InfoTile>
                    <InfoTile label="Tile Hash">
                      <p className="break-all font-mono text-xs text-slate-400">
                        {report.map_position.tile_hash}
                      </p>
                    </InfoTile>
                    <InfoTile label="Barycentric Anchor Weights">
                      <div className="space-y-1.5">
                        {report.map_position.barycentric.map((value, index) => (
                          <p key={`bary-${index}`} className="font-mono text-xs text-slate-300">
                            λ{index + 1}: {value.toFixed(4)}
                          </p>
                        ))}
                      </div>
                    </InfoTile>
                  </div>

                  <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
                    <div className="flex items-center gap-2 mb-2">
                      <MapPinned className="w-4 h-4 text-slate-500" />
                      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                        Tau Coordinates
                      </span>
                    </div>
                    <p className="mb-4 text-sm text-slate-400">
                      These values represent the artifact’s deterministic position
                      in a mathematical Penrose map space (five τ coordinates).
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                      {report.map_position.tau_vectors.map((value, index) => (
                        <div
                          key={`tau-${index}`}
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
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-500">
                  Map coordinates are not available for this artifact.
                </p>
              )}
            </Section>

            <Section
              title="Map Visualization"
              description="Penrose tiling fingerprint rendered from the artifact map position."
            >
              <div className="overflow-hidden rounded-2xl border border-white/8 bg-slate-900/40 p-3">
                <p className="mb-3 text-sm text-slate-400">
                  This visualization helps you inspect the structural signature
                  produced by the deterministic audit.
                </p>
                <img
                  src={`${API_URL}/api/report/${uploadId}/svg`}
                  alt="Penrose map visualization"
                  className="w-full rounded-xl border border-white/6 bg-slate-950/60"
                />
              </div>
            </Section>

            <Section
              title="Genesis Anchors & Ledger"
              description="Stable reference frame and chain continuity for this map position."
            >
              <div className="space-y-5">
                <InfoTile label="Genesis Frame">
                  <p className="text-sm text-slate-300">
                    This position is interpreted against the fixed Genesis frame:
                    the fine-structure constant, Einstein field equations, and
                    Boltzmann entropy.
                  </p>
                  <p className="mt-2 text-xs text-slate-500">
                    The barycentric values above show how this artifact resolves
                    relative to those fixed anchors.
                  </p>
                </InfoTile>

                {report.ledger && (
                  <div className="grid gap-4 md:grid-cols-2">
                    <InfoTile label="Ledger Entry Hash">
                      <p className="break-all font-mono text-xs text-slate-400">
                        {report.ledger.entry_hash}
                      </p>
                    </InfoTile>
                    <InfoTile label="Next State Hash">
                      <p className="break-all font-mono text-xs text-slate-400">
                        {report.ledger.next_state_hash || "Not available"}
                      </p>
                    </InfoTile>
                    <InfoTile label="Previous State">
                      <p className="break-all font-mono text-xs text-slate-400">
                        {report.ledger.prev_state || "Genesis-linked origin"}
                      </p>
                    </InfoTile>
                    <InfoTile label="Audit Content SHA-256">
                      <p className="break-all font-mono text-xs text-slate-400">
                        {report.ledger.audit_content_sha256}
                      </p>
                    </InfoTile>
                  </div>
                )}
              </div>
            </Section>

            {/* ── Audit Trail ── */}
            <Section
              title="Audit Trail"
              description="Traceability details for this deterministic audit run."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <InfoTile label="Triggered By">
                  <p className="text-sm text-slate-300 leading-6">
                    PASS97 upload flow (user-triggered audit request).
                  </p>
                </InfoTile>
                <InfoTile label="Timestamp" icon={CalendarClock}>
                  <p className="text-sm font-medium text-slate-300 leading-6">
                    {formatTimestamp(report.verification.timestamp)}
                  </p>
                </InfoTile>
                <InfoTile label="RIM-OS System Version" icon={Fingerprint} full>
                  <p className="text-sm text-slate-300 leading-6">
                    {String(euAiMeta?.schema ?? "unknown")}
                  </p>
                </InfoTile>
              </div>
            </Section>

            <BlockchainInfo
              block={report.artifact_block}
              chainHeight={report.chain_height}
            />

            {/* File Information */}
            <Section
              title="File Information"
              description="Core identifiers for the artifact that was mapped."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <InfoTile label="Report ID" icon={Fingerprint}>
                  <p className="break-all font-mono text-xs text-amber-200/80">
                    {uploadId}
                  </p>
                </InfoTile>
                <InfoTile label="Verification Date" icon={CalendarClock}>
                  <p className="text-sm font-medium text-slate-300">
                    {formatTimestamp(report.verification.timestamp)}
                  </p>
                </InfoTile>
                <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5 md:col-span-2">
                  <div className="flex items-center gap-2 mb-3">
                    <Fingerprint className="w-4 h-4 text-slate-500" />
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                      File Hash (SHA-256)
                    </span>
                  </div>
                  <p className="break-all font-mono text-xs leading-6 text-amber-200/70 rounded-xl border border-amber-300/15 bg-amber-300/5 p-3">
                    {report.file_hash}
                  </p>
                </div>
              </div>
            </Section>

            {/* Security Checks */}
            <Section
              title="Security Checks"
              description="Deterministic checks performed on the mapped artifact."
            >
              <div className="overflow-hidden rounded-2xl border border-white/8">
                {/* Header row */}
                <div className="grid grid-cols-[minmax(0,1.3fr),110px,minmax(0,1.4fr)] bg-slate-900/80 px-5 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  <div>Check Name</div>
                  <div>Status</div>
                  <div>Details</div>
                </div>
                {/* Rows */}
                <div className="divide-y divide-white/6">
                  {report.verification.checks.map((check, index) => {
                    const parsed = parseCheck(check);
                    const state = getCheckState(check);
                    return (
                      <div
                        key={`${check}-${index}`}
                        className="grid grid-cols-1 gap-3 px-5 py-4 md:grid-cols-[minmax(0,1.3fr),110px,minmax(0,1.4fr)] md:items-center hover:bg-white/2 transition-colors"
                      >
                        <div className="font-medium text-slate-200">
                          {parsed.name}
                        </div>
                        <div>
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${state.badge}`}
                          >
                            {state.icon}
                            {state.label}
                          </span>
                        </div>
                        <div className="text-sm text-slate-400">
                          {parsed.details}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <p className="mt-4 text-sm text-slate-400 leading-7">
                Security evidence here focuses on deterministic integrity signals (schema/genesis consistency),
                plus optional signature evidence when signature metadata is present. For production deployment,
                additional domain-specific and operational testing is recommended.
              </p>
            </Section>

          {/* ── Right column ── */}
          <div className="space-y-8">
            {/* KPI Summary */}
            <Section
              title="Position Summary"
              description="High-level status for this artifact position."
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/6 p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    Confidence
                  </p>
                  <p className={`mt-3 text-4xl font-bold ${tone.titleColor}`}>
                    {report.verification.confidence}%
                  </p>
                </div>
                <div className="rounded-2xl border border-sky-400/20 bg-sky-400/6 p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    Checks Completed
                  </p>
                  <p className="mt-3 text-4xl font-bold text-sky-300">
                    {checkCount}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5 sm:col-span-2">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    Signature Verification
                  </p>
                  <p
                    className={`mt-3 text-2xl font-bold ${signatureStatus === "Pass" ? "text-emerald-300" : signatureStatus === "Fail" ? "text-red-300" : "text-slate-400"}`}
                  >
                    {signatureStatus}
                  </p>
                  <p className="mt-2 text-xs text-slate-500 break-words">
                    {signatureCheck || "No signature check in report payload."}
                  </p>
                </div>
              </div>
            </Section>

            {/* Verification Metrics */}
            <Section
              title="Pipeline Metrics"
              description="Current values returned by the deterministic mapping pipeline."
            >
              <div className="space-y-3">
                {report.kpis.map((kpi) => (
                  <div
                    key={kpi.id}
                    className="rounded-2xl border border-white/8 bg-slate-900/60 p-5"
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-200">
                          {kpi.label}
                        </p>
                        {kpi.description && (
                          <p className="mt-0.5 text-xs text-slate-500">
                            {kpi.description}
                          </p>
                        )}
                      </div>
                      <span
                        className={`rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${kpiBadge(kpi.status)}`}
                      >
                        {kpi.status}
                      </span>
                    </div>
                    <p
                      className={`text-4xl font-bold ${kpiValueColor(kpi.status)}`}
                    >
                      {formatMetricValue(kpi.value)}
                    </p>
                  </div>
                ))}
              </div>
            </Section>

            {/* ── Warnings & Recommendations ── */}
            <Section
              title="Warnings & Recommendations"
              description="Actionable guidance based on detected anomalies and reliability."
            >
              <div className="space-y-3">
                <div
                  className={`rounded-2xl border p-5 ${
                    anomalyCount > 0
                      ? "border-amber-400/30 bg-amber-400/8"
                      : "border-emerald-400/20 bg-emerald-400/6"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    {anomalyCount > 0 ? (
                      <TriangleAlert className="w-4 h-4 text-amber-300" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    )}
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                      Warnings
                    </p>
                  </div>
                  <p className="mt-2 text-sm text-slate-300 leading-7">
                    {anomalyCount === 0
                      ? "No anomalies were detected."
                      : `${anomalyCount} anomaly${anomalyCount === 1 ? "" : "ies"} were detected. Review is recommended before production use.`}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    Reliability
                  </p>
                  <p className="mt-2 text-sm text-slate-300 leading-7">
                    Confidence is {report.verification.confidence}%. This is moderate reliability for deterministic structural checks.
                  </p>
                </div>
              </div>
            </Section>

            {/* ── Data Governance & Scope ── */}
            <Section
              title="Data Governance & Audit Scope"
              description="Clear statements on what the system analyzes (and what it cannot verify)."
            >
              <div className="space-y-3">
                <p className="text-sm text-slate-300 leading-7">
                  This system analyzes the uploaded model artifact as a deterministic binary object.
                  It evaluates structural integrity, deterministic mapping consistency, and anomaly signals on the artifact’s mapped representation.
                </p>
                <ul className="list-disc pl-5 text-sm text-slate-400 space-y-1">
                  <li>It does NOT analyze model behavior (inference) or real-world performance.</li>
                  <li>Training data source, dataset bias, and provenance cannot be verified from weights-only structural analysis.</li>
                  <li>Production safety and fairness require additional domain testing and governance.</li>
                </ul>
              </div>
            </Section>

            {/* ── Limitations ── */}
            <Section
              title="Limitations of This Analysis"
              description="Clear boundaries on what this report does—and does not—cover."
            >
              <div className="rounded-2xl border border-slate-400/20 bg-slate-900/40 p-5 space-y-3">
                <p className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <ListChecks className="w-4 h-4 text-slate-300" />
                  What this report does NOT cover
                </p>
                <p className="text-sm text-slate-300 leading-7">
                  This audit evaluates only the artifact&apos;s deterministic file structure.
                </p>
                <ul className="list-disc pl-5 text-sm text-slate-400 space-y-1">
                  <li>It does NOT test model behavior in real-world usage.</li>
                  <li>It does NOT verify training data quality or provenance.</li>
                  <li>It does NOT guarantee fairness or safety of outputs.</li>
                </ul>
              </div>
            </Section>

            {/* ── How to Use ── */}
            <Section
              title="How to Use This Report"
              description="Practical next steps for users."
            >
              <ul className="list-disc pl-5 text-sm text-slate-400 space-y-1">
                <li>
                  Use this report to verify file integrity and deterministic structural mapping.
                </li>
                <li>
                  Run additional domain validation for real-world performance before deployment.
                </li>
                <li>
                  Combine this report with any required governance or compliance checks for sensitive use cases.
                </li>
              </ul>
            </Section>

            {/* ── Post-audit monitoring ── */}
            <Section
              title="Post‑Audit Monitoring & Re‑Audit Triggers"
              description="Guidance for what to monitor after deployment and when to re-run the audit."
            >
              <div className="space-y-3">
                <p className="text-sm text-slate-300 leading-7">
                  Re-audit is recommended whenever the underlying weights artifact changes,
                  before deploying to production, and whenever monitoring signals indicate drift or integrity risk.
                </p>
                <ul className="list-disc pl-5 text-sm text-slate-400 space-y-1">
                  <li>Re-run the audit if you update the model weights file (different file hash/artifact).</li>
                  <li>Consider manual review and additional testing when anomalies are detected (anomaly signal count: {anomalyCount}).</li>
                  <li>Trigger escalation when human review is required or when risk classification is not Minimal Risk.</li>
                </ul>
              </div>
            </Section>

            {/* Downloads */}
            <Section
              title="Download Actions"
              description="Open or download the preserved report artifacts."
            >
              <div className="space-y-3">
                <a
                  href={`${API_URL}/api/report/${uploadId}/pdf`}
                  className="flex items-center justify-between rounded-2xl border border-white/8 bg-slate-900/50 px-5 py-4 hover:border-sky-400/40 hover:bg-sky-400/5 transition-all"
                >
                  <span className="font-medium text-slate-200">
                    PDF audit report
                  </span>
                  <Download className="w-4 h-4 text-sky-400" />
                </a>
                <a
                  href={`${API_URL}/api/report/${uploadId}/html`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between rounded-2xl border border-white/8 bg-slate-900/50 px-5 py-4 hover:border-amber-400/40 hover:bg-amber-400/5 transition-all"
                >
                  <span className="font-medium text-slate-200">
                    HTML report view
                  </span>
                  <FileCode2 className="w-4 h-4 text-amber-400" />
                </a>
                <a
                  href={`${API_URL}/api/report/${uploadId}/svg`}
                  className="flex items-center justify-between rounded-2xl border border-white/8 bg-slate-900/50 px-5 py-4 hover:border-violet-400/40 hover:bg-violet-400/5 transition-all"
                >
                  <span className="font-medium text-slate-200">
                    Penrose SVG artifact
                  </span>
                  <FileImage className="w-4 h-4 text-violet-400" />
                </a>
              </div>
            </Section>

            <div className="text-xs text-slate-400 text-center mt-8 border-t border-slate-800 pt-4">
              <strong>Regulatory Note:</strong> This report includes structured analytical outputs that may support
              evaluation under the{" "}
              <strong>EU AI Act (Regulation (EU) 2024/1689), Articles 9–15</strong>.
              The results are generated through deterministic mathematical analysis and are provided
              for informational purposes only. This report does not constitute a formal conformity
              assessment or certification under the EU AI Act.
            </div>

          </div>
        </div>

            {/* Audit Details */}
            <Section
              title="Audit Evidence"
              description="Compliance, legal scope, and supporting evidence preserved beneath the map layer."
            >
              <div className="space-y-5">
                {/* EU AI Act Summary (human-friendly) */}
                <div className="rounded-2xl border border-amber-400/15 bg-amber-400/6 p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-2">
                    EU AI Act Summary
                  </p>
                  <p className="text-sm font-semibold text-slate-200">
                    Classification: {riskLabel}
                  </p>
                  <p className="mt-1 text-sm text-slate-300">
                    Status: {complianceStatusPretty}
                  </p>
                  <p className="mt-3 text-sm text-slate-400 leading-7">
                    This means: the artifact meets basic deterministic integrity checks with risk signals interpreted through EU AI Act mapping. Review is recommended for production or sensitive use cases.
                  </p>
                </div>

                <InfoTile label="EU AI Act Mapping" icon={Scale}>
                  <p className="text-sm text-slate-300">
                    {report.eu_ai_act.assessment}
                  </p>
                  <p className="mt-2 text-xs text-slate-500">
                    Category: {riskLabel} - Reference:{" "}
                    {report.eu_ai_act.article_reference}
                  </p>
                </InfoTile>

                {report.EU_AI_ACT_HASH && (
                  <InfoTile label="EU AI Act Report Hash" icon={Fingerprint} full>
                    <p className="break-all font-mono text-xs leading-6 text-amber-200/70 rounded-xl border border-amber-300/15 bg-amber-300/5 p-3">
                      {report.EU_AI_ACT_HASH}
                    </p>
                  </InfoTile>
                )}

                {euAiConformity && (
                  <div className="grid gap-4 md:grid-cols-2">
                    <InfoTile label="EU AI Act Conformity">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-base font-semibold text-slate-200">
                          Classification: {riskLabel}
                        </p>
                        <span
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${complianceBadge}`}
                        >
                          {complianceStatusPretty}
                        </span>
                      </div>
                      <p className="mt-3 text-sm text-slate-300">
                        Why this classification:{" "}
                        {anomalyCount === 0
                          ? "no anomaly signals were detected in the deterministic audit."
                          : `${anomalyCount} anomaly signal${
                              anomalyCount === 1 ? "" : "s"
                            } were detected and mapped to EU AI Act risk thresholds.`}
                      </p>
                      <div className="mt-2 text-xs text-slate-500">
                        <div
                          className={`rounded-xl border p-3 ${
                            humanReviewNeeded
                              ? "border-amber-400/30 bg-amber-400/8"
                              : "border-emerald-400/20 bg-emerald-400/6"
                          }`}
                        >
                          <p className="text-sm font-semibold text-slate-200">
                            👤 Human Oversight
                          </p>
                          <p className="mt-1 text-xs text-slate-300 leading-5">
                            <strong>Responsible role:</strong> AI Auditor (Deterministic Structural Assessor) + Compliance Reviewer.
                          </p>
                          <p className="mt-2 text-xs text-slate-300 leading-5">
                            <strong>Manual review status:</strong>{" "}
                            {humanReviewNeeded ? "Required" : "Not required"}.
                          </p>
                          <p className="mt-2 text-xs text-slate-300 leading-5">
                            <strong>Human review guidance:</strong> {humanReviewGuidanceText}
                          </p>
                          <p className="mt-2 text-xs text-slate-300 leading-5">
                            <strong>Escalation condition (threshold-based):</strong>{" "}
                            escalation is triggered when the EU AI Act layer sets{" "}
                            <span className="font-mono">requires_human_review</span> based on audit thresholds (including anomaly signals and risk band), or when the audit outcome indicates Limited/High risk.
                          </p>
                        </div>
                      </div>
                    </InfoTile>
                    <InfoTile label="Layer Metadata">
                      <p className="text-sm text-slate-300">
                        {String(euAiMeta?.layer_version ?? "Unknown layer")}
                      </p>
                      <p className="mt-2 text-xs text-slate-500">
                        Generated for schema {String(euAiMeta?.schema ?? "unknown")}
                      </p>
                      <p className="mt-2 text-xs text-slate-500">
                        Target file: {String(euAiMeta?.target_file ?? "unknown")}
                      </p>
                    </InfoTile>
                  </div>
                )}

                {euAiArticles.length > 0 && (
                  <div className="grid gap-4 md:grid-cols-2">
                    {euAiArticles.map((article) => (
                      <div
                        key={article.key}
                        className="rounded-2xl border border-white/8 bg-slate-900/60 p-5"
                      >
                        <p className="text-sm font-semibold text-slate-200">
                          {article.title}
                        </p>
                        <p className="mt-2 text-sm leading-6 text-slate-400">
                          {article.summary}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                <InfoTile label="Legal Scope" icon={ListChecks}>
                  <p className="text-sm text-slate-300">
                    {report.legal_disclosures.weight_space_scope}
                  </p>
                </InfoTile>

                {euAiFull && (
                  <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-200">
                          EU AI Act Raw Payload
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          Full structured attachment returned by the backend.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setIsEuPayloadOpen(true)}
                        className="rounded-full border border-sky-400/30 bg-sky-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-sky-300 transition hover:border-sky-300/50 hover:bg-sky-300/15"
                      >
                        View Payload
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </Section>

          </div>

      </main>

      {euAiFull && isEuPayloadOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-5xl rounded-[2rem] border border-white/10 bg-slate-950 shadow-2xl shadow-black/50">
            <div className="flex items-center justify-between gap-4 border-b border-white/8 px-6 py-5">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  EU AI Act
                </p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                  Raw Payload
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setIsEuPayloadOpen(false)}
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300 transition hover:border-white/20 hover:bg-white/10"
              >
                Close
              </button>
            </div>
            <div className="p-6">
              <pre className="max-h-[70vh] overflow-auto rounded-2xl border border-white/8 bg-[#020817] p-5 text-xs leading-6 text-slate-300">
                {formatJson(euAiFull)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

