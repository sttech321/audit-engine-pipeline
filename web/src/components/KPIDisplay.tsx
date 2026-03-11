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

  return Number.isNaN(parsed.getTime())
    ? timestamp
    : parsed.toLocaleString();
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

  // Helper for KPI icons based on ID or Label
  const getKpiIcon = (kpi: KPI) => {
    if (kpi.label.includes("Score"))
      return <Shield className="w-5 h-5 text-blue-500" />;
    if (kpi.label.includes("Issues"))
      return <AlertTriangle className="w-5 h-5 text-purple-500" />;
    if (kpi.label.includes("Coverage"))
      return <Zap className="w-5 h-5 text-green-500" />;
    return <Info className="w-5 h-5 text-gray-500" />;
  };

  return (
    <div className="space-y-6">
      {/* Verification Status */}
      <div
        className={`
        p-6 rounded-xl border-2
        ${
          isVerified
            ? "bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800"
            : isWarning
            ? "bg-yellow-50 dark:bg-yellow-950/20 border-yellow-200 dark:border-yellow-800"
            : "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800"
        }
      `}
      >
        <div className="flex items-start gap-4">
          {isVerified ? (
            <CheckCircle className="w-8 h-8 text-green-600 flex-shrink-0" />
          ) : isWarning ? (
            <AlertTriangle className="w-8 h-8 text-yellow-600 flex-shrink-0" />
          ) : (
            <XCircle className="w-8 h-8 text-red-600 flex-shrink-0" />
          )}
          <div className="flex-1">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Verification Status: {verification.status}
              </h3>
              {metadata?.verification_mode && (
                <span className="ml-2 inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-900 px-3 py-1 text-xs font-semibold text-gray-700 dark:text-gray-200">
                  {metadata.verification_mode === "limited"
                    ? "Verification Mode: Limited Analysis"
                    : "Verification Mode: Full PASS97 Audit"}
                </span>
              )}
              <span className="text-sm font-medium text-gray-500">
                Confidence: {verification.confidence}%
              </span>
            </div>
            <div className="space-y-1 text-sm bg-white/50 dark:bg-black/20 p-4 rounded-lg">
              <h4 className="font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Pipeline Check Results:
              </h4>
              {verification.checks.map((check, idx) => {
                const isFail = /invalid|failed|anomaly|low confidence/i.test(
                  check,
                );
                return (
                  <div key={idx} className="flex items-center gap-2">
                    {isFail ? (
                      <XCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                    ) : (
                      <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
                    )}
                    <span
                      className={
                        isFail
                          ? "text-red-700 dark:text-red-400 font-semibold"
                          : "text-green-800 dark:text-green-200 font-medium"
                      }
                    >
                      {check}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
              <Clock className="w-3 h-3" />
              <span>
                Executed at {formatVerificationTimestamp(verification.timestamp)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {kpis.map((kpi) => (
          <div
            key={kpi.id}
            className="p-5 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {getKpiIcon(kpi)}
                <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                  {kpi.label}
                </h4>
              </div>
              <span
                className={`text-xs font-medium px-2 py-1 rounded-full 
                                ${kpi.status === "excellent" ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" : ""}
                                ${kpi.status === "good" ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" : ""}
                                ${kpi.status === "warning" ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200" : ""}
                            `}
              >
                {kpi.status}
              </span>
            </div>
            <p
              className={`text-3xl font-bold 
                            ${kpi.status === "excellent" ? "text-green-600 dark:text-green-400" : ""}
                            ${kpi.status === "good" ? "text-blue-600 dark:text-blue-400" : ""}
                            ${kpi.status === "warning" ? "text-yellow-600 dark:text-yellow-400" : ""}
                        `}
            >
              {kpi.value}
            </p>
            {kpi.description && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                {kpi.description}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* File Hash */}
      <div className="p-5 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Cryptographic File Hash (SHA-256)
        </h4>
        <p className="text-sm font-mono text-gray-700 dark:text-gray-300 break-all bg-gray-50 dark:bg-gray-900 p-3 rounded border border-gray-100 dark:border-gray-700">
          {fileHash}
        </p>
      </div>

      <div className="p-5 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Signature Verification
        </h4>
        <div className="flex items-start gap-3">
          {signatureVerified === true ? (
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
          ) : signatureVerified === false ? (
            <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          ) : (
            <Info className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" />
          )}
          <div className="text-sm text-gray-700 dark:text-gray-300">
            <p className="font-medium">
              {signatureVerified === true
                ? "Signed metadata verified"
                : signatureVerified === false
                  ? "Signed metadata failed verification"
                  : "No signature data available"}
            </p>
            {metadata?.public_key && (
              <p className="mt-1 font-mono text-xs text-gray-500 dark:text-gray-400">
                Public key: {metadata.public_key}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
