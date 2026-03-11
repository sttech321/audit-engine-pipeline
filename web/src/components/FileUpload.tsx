'use client';

import { FC, useState, useCallback } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { Upload, FileCheck, AlertCircle } from 'lucide-react';

interface FileUploadProps {
    onFileSelect: (file: File) => void;
    isLoading?: boolean;
    maxFileSizeBytes?: number;
}

const formatSize = (bytes: number) => {
    if (bytes >= 1024 * 1024 * 1024) {
        return `${(bytes / 1024 / 1024 / 1024).toFixed(0)} GB`;
    }
    return `${(bytes / 1024 / 1024).toFixed(0)} MB`;
};

export const FileUpload: FC<FileUploadProps> = ({ onFileSelect, isLoading, maxFileSizeBytes }) => {
    const [error, setError] = useState<string | null>(null);

    const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
        setError(null);

        if (rejectedFiles.length > 0) {
            const firstError = rejectedFiles[0]?.errors?.[0]?.code;
            if (firstError === 'file-too-large' && maxFileSizeBytes) {
                setError(`File too large. Maximum size is ${formatSize(maxFileSizeBytes)}.`);
                return;
            }
            setError('Unable to process this file. Please try a different file or contact support.');
            return;
        }

        if (acceptedFiles.length > 0) {
            onFileSelect(acceptedFiles[0]);
        }
    }, [maxFileSizeBytes, onFileSelect]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        // Any file type is allowed; size limits and backend logic decide
        // whether full PASS97 audit or limited analysis is performed.
        maxSize: maxFileSizeBytes,
        maxFiles: 1,
        disabled: isLoading,
    });

    return (
        <div className="w-full">
            <div
                {...getRootProps()}
                className={`
          border-2 border-dashed rounded-xl p-12 text-center cursor-pointer
          transition-all duration-200
          ${isDragActive
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/20'
                        : 'border-gray-300 dark:border-gray-700 hover:border-blue-400'
                    }
          ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
        `}
            >
                <input {...getInputProps()} />

                <div className="flex flex-col items-center gap-4">
                    {isDragActive ? (
                        <FileCheck className="w-16 h-16 text-blue-500" />
                    ) : (
                        <Upload className="w-16 h-16 text-gray-400" />
                    )}

                    <div>
                        <p className="text-lg font-semibold text-gray-700 dark:text-gray-300">
                            {isDragActive ? 'Drop file here' : 'Drag & drop audit file'}
                        </p>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                            or click to browse any file type
                        </p>
                    </div>
                </div>
            </div>

            {error && (
                <div className="mt-4 p-4 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
                </div>
            )}
        </div>
    );
};
