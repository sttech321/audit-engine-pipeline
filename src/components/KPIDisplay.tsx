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
import type { KPI, VerificationStatus } from "../../../shared/types";

interface KPIDisplayProps {
  kpis: KPI[];
  verification: VerificationStatus;
  fileHash: string;
}

export const KPIDisplay: FC<KPIDisplayProps> = ({
  kpis,
  verification,
  fileHash,
}) => {
  const isVerified =
    verification.status === "Verified" ||
    verification.status === "Verified with Warnings";
  const isWarning = verification.status === "Verified with Warnings";

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
                Executed at{" "}
                {new Date(
                  parseFloat(verification.timestamp) * 1000,
                ).toLocaleString()}
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
    </div>
  );
};
