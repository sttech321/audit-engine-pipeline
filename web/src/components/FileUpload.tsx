"use client";

import { FC, useState, useCallback } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { Upload, FileCheck, AlertCircle } from "lucide-react";

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  isLoading?: boolean;
  maxFileSizeBytes?: number;
}

const formatSize = (bytes: number) => {
  if (bytes >= 1024 * 1024 * 1024)
    return `${(bytes / 1024 / 1024 / 1024).toFixed(0)} GB`;
  return `${(bytes / 1024 / 1024).toFixed(0)} MB`;
};

export const FileUpload: FC<FileUploadProps> = ({
  onFileSelect,
  isLoading,
  maxFileSizeBytes,
}) => {
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      setError(null);
      if (rejectedFiles.length > 0) {
        const firstError = rejectedFiles[0]?.errors?.[0]?.code;
        if (firstError === "file-too-large" && maxFileSizeBytes) {
          setError(
            `File too large. Maximum size is ${formatSize(maxFileSizeBytes)}.`,
          );
          return;
        }
        setError("Unable to process this file. Please try a different file.");
        return;
      }
      if (acceptedFiles.length > 0) onFileSelect(acceptedFiles[0]);
    },
    [maxFileSizeBytes, onFileSelect],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxSize: maxFileSizeBytes,
    maxFiles: 1,
    disabled: isLoading,
  });

  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={`
                    relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer
                    transition-all duration-300 overflow-hidden
                    ${
                      isDragActive
                        ? "border-amber-400 bg-amber-300/10 shadow-[0_0_40px_rgba(251,191,36,0.25)]"
                        : "border-white/15 bg-slate-900/50 hover:border-amber-400/50 hover:bg-amber-300/5"
                    }
                    ${isLoading ? "opacity-40 cursor-not-allowed" : ""}
                `}
      >
        <input {...getInputProps()} />

        {/* Subtle grid pattern */}
        <div
          className="pointer-events-none absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              "radial-gradient(circle, rgba(251,191,36,0.3) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />

        <div className="relative flex flex-col items-center gap-5">
          <div
            className={`rounded-2xl p-4 transition-all duration-300 ${isDragActive ? "bg-amber-300/20" : "bg-slate-800/60"}`}
          >
            {isDragActive ? (
              <FileCheck className="w-12 h-12 text-amber-300" />
            ) : (
              <Upload className="w-12 h-12 text-slate-400" />
            )}
          </div>

          <div>
            <p className="text-lg font-semibold text-slate-200">
              {isDragActive
                ? "Release to map artifact"
                : "Drag & drop your artifact"}
            </p>
            <p className="text-sm text-slate-500 mt-1.5">
              or{" "}
              <span className="text-amber-300/80 hover:text-amber-300 cursor-pointer">
                browse a supported artifact
              </span>
            </p>
            {maxFileSizeBytes && (
              <p className="text-xs text-slate-600 mt-2">
                Up to {formatSize(maxFileSizeBytes)}
              </p>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}
    </div>
  );
};
