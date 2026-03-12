"use client";

import { FC } from "react";
import {
  Shield,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Info,
  Zap,
} from "lucide-react";
import type {
  KPI,
  UploadMetadata,
  VerificationStatus,
} from "../../../shared/types";

interface KPIDisplayProps {
  kpis: KPI[];
  verification: VerificationStatus;
  fileHash: string;
  metadata?: UploadMetadata;
}

const formatVerificationTimestamp = (timestamp: string) => {
  if (!timestamp) return "Timestamp unavailable";
  const numeric = Number(timestamp);
  const parsed = Number.isNaN(numeric)
    ? new Date(timestamp)
    : new Date(numeric * 1000);
  return Number.isNaN(parsed.getTime()) ? timestamp : parsed.toLocaleString();
};

export const KPIDisplay: FC<KPIDisplayProps> = ({
  kpis,
  verification,
  fileHash,
  metadata,
}) => {
  const isVerified =
    verification.status === "Verified" ||
    verification.status === "Verified with Warnings";
  const isWarning = verification.status === "Verified with Warnings";
  const signatureVerified = metadata?.signature_verified;

  const getDisplayLabel = (label: string) => {
    if (label === "Audit Score") return "Integrity Score";
    if (label === "Issues Found") return "Anomaly Count";
    if (label === "KAG Score") return "Separability Score";
    return label;
  };

  const getDisplayDescription = (kpi: KPI) => {
    if (kpi.label === "Audit Score") {
      return "Overall integrity of this mapped artifact position (0-100).";
    }
    if (kpi.label === "Issues Found") {
      return "Number of anomalous regions detected while resolving this position.";
    }
    if (kpi.label === "KAG Score") {
      return "Kolmogorov-Arnold separability for the artifact's coordinate structure.";
    }
    if (kpi.label === "Coverage") {
      return "How completely the artifact resolved through the deterministic mapping flow.";
    }
    if (kpi.label === "Penrose Sector") {
      return "Internal Penrose geometry indicator preserved from the existing engine output.";
    }
    return kpi.description;
  };

  const getKpiIcon = (kpi: KPI) => {
    if (kpi.label.includes("Score"))
      return <Shield className="w-5 h-5 text-sky-400" />;
    if (kpi.label.includes("Issues"))
      return <AlertTriangle className="w-5 h-5 text-violet-400" />;
    if (kpi.label.includes("Coverage"))
      return <Zap className="w-5 h-5 text-emerald-400" />;
    return <Info className="w-5 h-5 text-slate-500" />;
  };

  const statusConfig =
    isVerified && !isWarning
      ? {
          border: "border-emerald-400/30",
          bg: "bg-emerald-400/8",
          icon: (
            <CheckCircle className="w-8 h-8 text-emerald-400 flex-shrink-0" />
          ),
          titleColor: "text-emerald-300",
          badgeClass: "bg-emerald-400/15 text-emerald-300",
        }
      : isWarning
        ? {
            border: "border-amber-400/30",
            bg: "bg-amber-400/8",
            icon: (
              <AlertTriangle className="w-8 h-8 text-amber-400 flex-shrink-0" />
            ),
            titleColor: "text-amber-300",
            badgeClass: "bg-amber-400/15 text-amber-300",
          }
        : {
            border: "border-red-500/30",
            bg: "bg-red-500/8",
            icon: <XCircle className="w-8 h-8 text-red-400 flex-shrink-0" />,
            titleColor: "text-red-300",
            badgeClass: "bg-red-500/15 text-red-300",
          };

  const kpiValueColor = (status: string) =>
    status === "excellent"
      ? "text-emerald-300"
      : status === "good"
        ? "text-sky-300"
        : status === "warning"
          ? "text-amber-300"
          : "text-slate-300";

  const kpiBadge = (status: string) =>
    status === "excellent"
      ? "bg-emerald-400/15 text-emerald-300"
      : status === "good"
        ? "bg-sky-400/15 text-sky-300"
        : status === "warning"
          ? "bg-amber-400/15 text-amber-300"
          : "bg-slate-700/50 text-slate-400";

  return (
    <div className="space-y-6">
      {/* ── Verification status ── */}
      <div
        className={`rounded-2xl border p-6 ${statusConfig.border} ${statusConfig.bg} backdrop-blur`}
      >
        <div className="flex items-start gap-4">
          {statusConfig.icon}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-3 mb-3">
              <h3
                className={`text-lg font-semibold ${statusConfig.titleColor}`}
              >
                {verification.status}
              </h3>
              {metadata?.verification_mode && (
                <span
                  className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${statusConfig.badgeClass}`}
                >
                  {metadata.verification_mode === "limited"
                    ? "Limited Analysis"
                    : "Full PASS97 Audit"}
                </span>
              )}
              <span className="ml-auto text-sm font-semibold text-slate-300">
                {verification.confidence}% confidence
              </span>
            </div>

            <div className="space-y-1.5 rounded-xl border border-white/6 bg-slate-950/50 p-4">
              <h4 className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-2">
                Position resolution checks
              </h4>
              {verification.checks.map((check, idx) => {
                const isFail = /invalid|failed|anomaly|low confidence/i.test(
                  check,
                );
                return (
                  <div key={idx} className="flex items-center gap-2">
                    {isFail ? (
                      <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                    ) : (
                      <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    )}
                    <span
                      className={`text-sm ${isFail ? "text-red-300 font-semibold" : "text-emerald-200"}`}
                    >
                      {check}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
              <Clock className="w-3 h-3" />
              <span>
                Executed at{" "}
                {formatVerificationTimestamp(verification.timestamp)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── KPI grid ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {kpis.map((kpi) => (
          <div
            key={kpi.id}
            className="rounded-2xl border border-white/8 bg-slate-950/60 p-5 backdrop-blur"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                {getKpiIcon(kpi)}
                <h4 className="font-semibold text-slate-200">
                  {getDisplayLabel(kpi.label)}
                </h4>
              </div>
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-full ${kpiBadge(kpi.status)}`}
              >
                {kpi.status}
              </span>
            </div>
            <p className={`text-3xl font-bold ${kpiValueColor(kpi.status)}`}>
              {kpi.value}
            </p>
            {getDisplayDescription(kpi) && (
              <p className="text-sm text-slate-500 mt-2">
                {getDisplayDescription(kpi)}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* ── File hash ── */}
      <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-5 backdrop-blur">
        <h4 className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-3">
          Artifact Hash (SHA-256)
        </h4>
        <p className="text-sm font-mono text-amber-200/80 break-all rounded-xl border border-amber-300/15 bg-amber-300/5 p-3">
          {fileHash}
        </p>
      </div>

      {/* ── Signature ── */}
      <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-5 backdrop-blur">
        <h4 className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-3">
          Signature Evidence
        </h4>
        <div className="flex items-start gap-3">
          {signatureVerified === true ? (
            <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
          ) : signatureVerified === false ? (
            <XCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          ) : (
            <Info className="w-5 h-5 text-slate-500 flex-shrink-0 mt-0.5" />
          )}
          <div>
            <p
              className={`text-sm font-medium ${
                signatureVerified === true
                  ? "text-emerald-300"
                  : signatureVerified === false
                    ? "text-red-300"
                    : "text-slate-400"
              }`}
            >
              {signatureVerified === true
                ? "Signed metadata verified"
                : signatureVerified === false
                  ? "Signed metadata failed verification"
                  : "No signature data available"}
            </p>
            {metadata?.public_key && (
              <p className="mt-1 font-mono text-xs text-slate-500">
                Public key: {metadata.public_key}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
