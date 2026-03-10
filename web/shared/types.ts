export interface FileInfo {
  name: string;
  size: number;
  type: string;
}

export interface KPI {
  id: string;
  label: string;
  value: string | number;
  trend: string;
  status: string;
  description?: string;
}

export interface VerificationStatus {
  status: string;
  confidence: number;
  timestamp: string;
  checks: string[];
}

export interface UploadResponse {
  fileInfo: FileInfo;
  kpis: KPI[];
  verification: VerificationStatus;
  fileHash: string;
  uploadId: string;
  metadata: Record<string, any>;
}

export interface MintPrepareResponse {
  metadata: { url: string };
  mintHash: string;
  nftMetadata: { name: string; symbol: string };
}
