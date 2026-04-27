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

export interface UploadMetadata {
  name?: string;
  description?: string;
  attributes?: Array<{ trait_type: string; value: string | number }>;
  signature_verified?: boolean;
  public_key?: string;
  artifact_format?: string;
  artifact_version?: string;
  artifact_id?: string;
  verification_mode?: "full" | "limited";
  verification_mode_reason?: string;
}

export interface UploadResponse {
  fileInfo: FileInfo;
  kpis: KPI[];
  verification: VerificationStatus;
  fileHash: string;
  uploadId: string;
  metadata: UploadMetadata;
  artifactBlock?: ArtifactBlock | null;
}

export interface MintPrepareResponse {
  metadata: { url: string; provider?: string | null; fallbackUsed?: boolean };
  mintHash: string;
  nftMetadata: { name: string; symbol: string };
}

export interface IpfsUploadResponse {
  url: string;
  cid: string;
  provider?: string | null;
  fallbackUsed?: boolean;
}

export interface RiskBadge {
  level: string;
  score: number;
  label: string;
  color: string;
}

export interface EuAiActCompliance {
  category: string;
  article_reference: string;
  requirements: string[];
  assessment: string;
  disclaimer: string;
}

export interface LedgerInfo {
  ledger_id: string;
  sequence_number: number;
  prev_block_hash?: string | null;
  block_hash?: string | null;
  audit_content_sha256: string;
  entry_hash: string;
}

export interface LegalDisclosures {
  weight_space_scope: string;
  notified_body?: string | null;
  out_of_scope: string[];
  version: string;
}

export interface MapPosition {
  tau_vectors: number[];
  barycentric: number[];
  manifold_hash: string;
  tile_hash: string;
}

export interface ArtifactBlock {
  index: number;
  timestamp: string;
  artifact_hash: string;
  pipeline_version?: string | null;
  chain_seed_at_commit?: string | null;
  tau_vectors: number[];
  manifold_hash: string;
  tile_hash: string;
  barycentric: number[];
  prev_block_hash?: string | null;
  block_hash: string;
  type?: string | null;
  anchors?: string[] | null;
}

export interface Anomaly {
  anomaly_type: string;
  stage: string;
  severity: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface ExtendedAuditResult {
  kpis: KPI[];
  verification: VerificationStatus;
  file_hash: string;
  anomalies: Anomaly[];
  risk_badge: RiskBadge;
  eu_ai_act: EuAiActCompliance;
  EU_AI_ACT_FULL?: Record<string, unknown> | null;
  EU_AI_ACT_HASH?: string | null;
  ledger?: LedgerInfo | null;
  legal_disclosures: LegalDisclosures;
  penrose_details?: Record<string, unknown> | null;
  map_position?: MapPosition | null;
  artifact_block?: ArtifactBlock | null;
  tile_hash?: string | null;
}
