# RIMOS - Comprehensive Developer Guide

> Complete technical documentation for developers working on RIMOS (Review & Integrity Mapping of Offensive Schemes)

**Table of Contents**

- [Project Overview](#project-overview)
- [Architecture Overview](#architecture-overview)
- [Backend Development](#backend-development)
- [Frontend Development](#frontend-development)
- [Pipeline Process (Detailed)](#pipeline-process-detailed)
- [API Reference](#api-reference)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Project Overview

### What is RIMOS?

**RIMOS** is an AI artifact review and certification system that:

1. **Accepts** binary AI model files (`.lm3z`, `.rim0`, `.rim95`, `.safetensors`, `.bin`, `.gguf`, `.pt`, `.pth`, `.ckpt`, `.onnx`)
2. **Processes** them through a deterministic mathematical pipeline (RIM-OS v2 engine)
3. **Generates** integrity scores (0–100), risk levels (LOW/MEDIUM/HIGH), and anomaly reports
4. **Maps** artifact positions onto a Penrose tiling (infinite, non-repeating mathematical structure)
5. **Records** all positions in an internal blockchain ledger
6. **Issues** optional NFT certificates on Solana

### Key Concepts

| Term                | Definition                                                                                                   |
| ------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Penrose Tiling**  | Infinite, aperiodic mathematical map used as coordinate system for artifacts                                 |
| **Genesis Mints**   | Fixed reference anchors (fine-structure constant, Einstein equations, Boltzmann entropy) that orient the map |
| **Tau Vectors**     | 5-dimensional coordinates showing artifact's exact position on the Penrose map                               |
| **Artifact Block**  | Blockchain entry containing artifact hash, tau vectors, and position metadata                                |
| **RIM-OS v2**       | Core deterministic math engine that processes files and assigns map positions                                |
| **Integrity Score** | 0–100 metric combining entropy (30%), Penrose match (40%), and anomaly detection (30%)                       |
| **Risk Level**      | Classification (LOW/MEDIUM/HIGH) based on integrity score                                                    |

### Project Stack

**Backend:**

- Python 3.9+
- FastAPI (async web framework)
- Pydantic (data validation)
- pytest (testing)
- aiofiles (async file handling)

**Frontend:**

- Next.js 16 (React framework)
- TypeScript
- Solana Web3.js (blockchain)
- Tailwind CSS 4 (styling)
- Framer Motion (animations)

---

## Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         RIMOS SYSTEM                            │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │                    FRONTEND (Next.js)                    │
    │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │
    │  │FileUpload   │  │KPIDisplay    │  │MintFlow      │   │
    │  │Component    │  │Component     │  │(NFT Minting) │   │
    │  └─────────────┘  └──────────────┘  └──────────────┘   │
    └──────────────────────────────────────────────────────────┘
                              ↕
    ┌──────────────────────────────────────────────────────────┐
    │                   BACKEND (FastAPI)                      │
    │                                                          │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │           API Routers (Endpoints)                 │  │
    │  │  • upload/          • chunked_upload/            │  │
    │  │  • mint/            • report/                     │  │
    │  └────────────────────────────────────────────────────┘  │
    │                         ↓                                │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │           Services Layer                          │  │
    │  │  • chunked_upload_service.py                      │  │
    │  │  • file_validation.py                            │  │
    │  │  • artifact_chain.py                             │  │
    │  │  • metadata_parser.py                            │  │
    │  └────────────────────────────────────────────────────┘  │
    │                         ↓                                │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │         RIM-OS v2 (Core Engine)                  │  │
    │  │  • rim_wrapper.py → rim_os_v2.py                │  │
    │  │  • Deterministic Math Pipeline                   │  │
    │  │  • Gödel Encoding → p-adic → NTT → KAG → Penrose│  │
    │  └────────────────────────────────────────────────────┘  │
    │                         ↓                                │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │      Report Generation & Output                   │  │
    │  │  • pdf_generator.py                              │  │
    │  │  • svg_generator.py                              │  │
    │  │  • metadata_parser.py                            │  │
    │  └────────────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────────────┘
                              ↕
    ┌──────────────────────────────────────────────────────────┐
    │              Storage & External Services                 │
    │  • File System (chunk storage)                          │
    │  • Artifact Chain (blockchain ledger)                   │
    │  • IPFS Service (NFT metadata)                          │
    │  • Solana Blockchain (NFT minting)                      │
    └──────────────────────────────────────────────────────────┘
```

### Data Flow Architecture

```
UPLOAD → VALIDATION → CHUNKING → STORAGE → AUDIT ENGINE → REPORT → RESPONSE
   ↓          ↓          ↓         ↓           ↓           ↓         ↓
Frontend    File       Split    Temp       RIM-OS      PDF/SVG    KPIs +
Sends      Types,      into    Files      Processes   Generated  Blockchain
File       Size        20MB    on Disk    Through      for        Entry
           Checks               Math       Download
```

---

## Backend Development

### Directory Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app setup & root route
│   ├── config.py                  # Configuration settings
│   ├── dependencies.py            # Shared dependencies
│   ├── logging_config.py          # Logging setup
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py             # Core data schemas (UploadResponse, etc.)
│   │   ├── common_schemas.py      # Shared data structures
│   │   ├── upload_schemas.py      # Upload-specific schemas
│   │   ├── chunked_upload_schemas.py
│   │   ├── mint_schemas.py        # NFT minting schemas
│   │   ├── error_schemas.py       # Error responses
│   │   └── metadata_schemas.py    # Metadata structures
│   ├── routers/
│   │   ├── upload.py              # POST /api/upload (single file)
│   │   ├── chunked_upload.py      # /api/upload/chunked/* (large files)
│   │   ├── mint.py                # /api/mint/* (NFT minting)
│   │   └── report.py              # /api/report/* (report generation)
│   ├── services/
│   │   ├── chunked_upload_service.py    # Upload session management
│   │   ├── file_validation.py           # File type/size validation
│   │   ├── rim_wrapper.py               # RIM-OS v2 wrapper
│   │   ├── signature_verification.py    # Ed25519 signature checks
│   │   ├── metadata_parser.py           # Artifact metadata extraction
│   │   ├── artifact_chain.py            # Blockchain ledger management
│   │   ├── pdf_generator.py             # PDF report generation
│   │   ├── svg_generator.py             # Penrose tiling visualization
│   │   ├── ipfs_service.py              # IPFS metadata preparation
│   │   ├── abuse_protection.py          # Rate limiting
│   │   └── worker_executor.py           # Background job execution
│   └── utils/
│       ├── __init__.py
│       └── penrose.py              # Penrose tiling math utilities
├── rim_os_v2.py                    # Core audit engine (RIM-OS)
├── eu_ai_act_layer.py              # EU AI Act compliance checks
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Pytest configuration
├── tests/
│   ├── test_*.py                   # Test files for each component
│   └── conftest.py                 # Pytest fixtures & setup
└── data/
    ├── artifact_chain.json         # Blockchain ledger
    └── report_cache/               # Cached reports
        ├── {upload_id}.json        # Individual report cache
        └── ...
```

### Core Backend Files Explained

#### 1. `main.py` - FastAPI Application Setup

**Purpose:** Initializes the FastAPI application, configures CORS, middleware, and mounts all routers.

**Key responsibilities:**

- Create FastAPI app instance
- Configure CORS for frontend communication
- Setup logging
- Mount routers (upload, chunked_upload, mint, report)
- Define root health check endpoint

**Path:** [app/main.py](../backend/app/main.py)

#### 2. `rim_os_v2.py` - The RIM-OS Audit Engine

**Purpose:** Core mathematical engine that processes files and calculates artifact positions.

**Key functions:**

```python
run_rim_audit(file_path: str) → AuditResult
# Main entry point for file auditing
```

**Pipeline process:**

1. Read file in 1 MB chunks
2. For each chunk: Gödel encode → p-adic lift → NTT fingerprint → KAG grid → Penrose transform
3. Compute metrics: entropy, chi-squared, autocorrelation, Penrose match, KAG separability
4. Detect anomalies (z-score > ±3σ)
5. Calculate final integrity score and risk level
6. Output tau vectors (map coordinates)

**Path:** [rim_os_v2.py](../backend/rim_os_v2.py)

#### 3. `chunked_upload_service.py` - Upload Session Management

**Purpose:** Handles large file uploads in 20 MB chunks with resumability and parallel processing.

**Key functions:**

```python
create_upload_session(file_name: str) → str  # Returns upload_id
store_chunk(upload_id: str, chunk_index: int, chunk_data: bytes) → None
get_upload_status(upload_id: str) → UploadStatus
complete_upload(upload_id: str) → None  # Assembles chunks, triggers audit
```

**Features:**

- Resumable uploads (client can retry failed chunks)
- 8 parallel chunks supported
- 20 MB per chunk size limit
- Temporary storage until completion
- Automatic cleanup on completion

**Path:** [services/chunked_upload_service.py](../backend/app/services/chunked_upload_service.py)

#### 4. `rim_wrapper.py` - RIM-OS Interface

**Purpose:** Provides high-level wrapper around RIM-OS v2 engine.

**Key functions:**

```python
run_rim_audit(file_path: str) → ExtendedAuditResult
# Calls rim_os_v2.run_rim_audit() and wraps result
```

**Path:** [services/rim_wrapper.py](../backend/app/services/rim_wrapper.py)

#### 5. `file_validation.py` - File Validation

**Purpose:** Validates uploaded files before processing.

**Validations:**

- File extension (whitelist: `.lm3z`, `.rim0`, `.rim95`, `.safetensors`, `.bin`, `.gguf`, `.pt`, `.pth`, `.ckpt`, `.onnx`)
- File size (max 10 GB)
- MIME type checking
- Streaming reads to avoid memory overload

**Path:** [services/file_validation.py](../backend/app/services/file_validation.py)

#### 6. `pdf_generator.py` - Report Generation

**Purpose:** Generates downloadable PDF reports from audit results.

**Contents:**

- Audit score and KPIs
- Risk badge and risk level
- Anomaly list with details
- File hash and metadata
- Blockchain entry information
- UUID and timestamp

**Path:** [services/pdf_generator.py](../backend/app/services/pdf_generator.py)

#### 7. `artifact_chain.py` - Blockchain Ledger

**Purpose:** Maintains internal blockchain of artifact positions.

**Operations:**

- Create new artifact block with tau vectors
- Link to previous block (hash chain)
- Store in `data/artifact_chain.json`
- Retrieve artifact history

**Path:** [services/artifact_chain.py](../backend/app/services/artifact_chain.py)

### Backend Data Models (Schemas)

**Location:** [models/schemas.py](../backend/app/models/schemas.py)

#### Key Schemas:

```python
class KPI:
    label: str          # e.g., "Integrity Score"
    value: str or int   # e.g., "87"
    status: str         # "good", "warning", "critical"

class RiskBadge:
    level: str          # "LOW", "MEDIUM", "HIGH"
    score: int          # 0-100

class ArtifactBlock:
    index: int          # Position in chain
    artifact_hash: str  # SHA-256 of file
    tau_vectors: List[float]  # 5D coordinates on Penrose map
    manifold_hash: str  # Position hash
    timestamp: datetime

class UploadResponse:
    upload_id: str
    file_name: str
    file_size: int
    file_hash: str
    kpis: List[KPI]
    verification: VerificationStatus
    artifact_block: ArtifactBlock
    message: str
```

---

## Frontend Development

### Directory Structure

```
web/
├── src/
│   ├── app/
│   │   ├── globals.css           # Global styles
│   │   ├── page.tsx              # Landing page
│   │   ├── layout.tsx            # Root layout
│   │   ├── upload/
│   │   │   └── page.tsx          # Upload detail page
│   │   └── report/
│   │       └── page.tsx          # Report view page
│   ├── components/
│   │   ├── FileUpload.tsx        # Drag-drop file input
│   │   ├── KPIDisplay.tsx        # KPI grid visualization
│   │   ├── BlockchainInfo.tsx    # Artifact block display
│   │   ├── MintFlow.tsx          # NFT minting wizard
│   │   ├── WalletProvider.tsx    # Solana wallet setup
│   │   ├── ReportViewer.tsx      # PDF/HTML/SVG viewer
│   │   └── StatusIndicator.tsx   # Upload progress indicator
│   └── lib/
│       ├── api.ts                # API client functions
│       ├── solana.ts             # Solana utilities
│       └── utils.ts              # Helper functions
├── package.json
├── tsconfig.json
├── next.config.ts
├── tailwind.config.ts
└── postcss.config.mjs
```

### Frontend Components Explained

#### 1. **FileUpload Component**

**Purpose:** File selection interface with drag-and-drop, validation, and upload handling.

**Features:**

- Drag-and-drop zone
- File size validation (< 10 GB)
- Supported file type indicators
- Progress bar for upload
- Error messaging

**Props:**

```typescript
interface FileUploadProps {
    onUploadStart: (uploadId: string) => void;
    onUploadProgress: (percentage: number) => void;
    onUploadComplete: (result: UploadResponse) => void;
    onError: (error: Error) => void;
}
```

#### 2. **KPIDisplay Component**

**Purpose:** Displays audit results in grid format with visual indicators.

**Displays:**

- Integrity Score (0-100) with color coding
- Risk Level (LOW/MEDIUM/HIGH) with badge
- Anomalies Found (count)
- KAG Score (diagnostic)
- Coverage (% of file analyzed)
- Penrose Sector (map location)

**Props:**

```typescript
interface KPIDisplayProps {
    kpis: KPI[];
    riskLevel: string;
    integrityScore: number;
}
```

#### 3. **BlockchainInfo Component**

**Purpose:** Displays artifact blockchain entry and position on Penrose map.

**Shows:**

- Artifact Hash (SHA-256)
- Tau Vectors (5D coordinates)
- Manifold Hash
- Block Index in chain
- Genesis Mint references

**Props:**

```typescript
interface BlockchainInfoProps {
    artifactBlock: ArtifactBlock;
}
```

#### 4. **MintFlow Component**

**Purpose:** Multi-step NFT minting wizard for Solana.

**Steps:**

1. Connect Solana wallet (Phantom/Solflare)
2. Review metadata
3. Prepare IPFS upload
4. Create NFT on Solana Devnet
5. Confirm transaction
6. Display NFT URL

**Props:**

```typescript
interface MintFlowProps {
    uploadId: string;
    artifactHash: string;
    onMintComplete: (nftUrl: string) => void;
}
```

#### 5. **API Client Functions**

**Location:** `src/lib/api.ts`

**Key functions:**

```typescript
// Upload & Audit
uploadFile(file: File): Promise<UploadResponse>
uploadFileChunked(file: File): Promise<{uploadId: string}>
getUploadStatus(uploadId: string): Promise<UploadStatus>
completeChunkedUpload(uploadId: string): Promise<UploadResponse>

// Reports
getReportPDF(uploadId: string): Promise<Blob>
getReportHTML(uploadId: string): Promise<string>
getReportSVG(uploadId: string): Promise<string>

// NFT Minting
prepareMintMetadata(uploadId: string): Promise<MintMetadata>
finalizeMint(uploadId: string, signature: string): Promise<MintResult>
```

---

## Pipeline Process (Detailed)

### Complete End-to-End Flow

```
┌────────────────────────────────────────────────────────────────┐
│ STEP 1: USER UPLOADS FILE                                      │
└────────────────────────────────────────────────────────────────┘

  Frontend (FileUpload component)
  ├─ User drags file onto component
  ├─ Validates file type (extension check)
  ├─ Validates file size (< 10 GB)
  └─ Chooses upload method based on size:
     ├─ If < 100 MB: Single upload (POST /api/upload)
     └─ If ≥ 100 MB: Chunked upload (POST /api/upload/chunked/init + PUT chunks)
                        │
                        └─ 20 MB per chunk, up to 8 parallel
                        └─ Resumable (retry failed chunks)

┌────────────────────────────────────────────────────────────────┐
│ STEP 2: BACKEND FILE VALIDATION                                │
└────────────────────────────────────────────────────────────────┘

  Backend Validation (file_validation.py)
  ├─ Verify file extension against whitelist
  ├─ Check file size limits (1 KB - 10 GB)
  ├─ MIME type validation
  ├─ Signature verification (if provided)
  └─ Save file to temp location

  If chunked:
  ├─ ChunkedUploadService.create_upload_session()
  │  └─ Generate upload_id (UUID)
  │
  ├─ For each chunk received:
  │  └─ ChunkedUploadService.store_chunk()
  │     ├─ Write chunk to temp file
  │     ├─ Track completion status
  │     └─ Return status (HTTP 200)
  │
  └─ ChunkedUploadService.complete_upload()
     ├─ Assemble all chunks into single file
     ├─ Delete individual chunk files
     └─ Proceed to RIM-OS audit

┌────────────────────────────────────────────────────────────────┐
│ STEP 3: RIM-OS AUDIT ENGINE (rim_os_v2.py)                    │
│ This is where the mathematical magic happens                   │
└────────────────────────────────────────────────────────────────┘

  run_rim_audit(file_path)
  │
  ├─ CHUNK PROCESSING LOOP
  │  │ Read file in 1 MB chunks
  │  │
  │  └─ For each chunk:
  │     │
  │     ├─ GÖDEL ENCODING
  │     │  │ Convert binary bytes to prime exponents
  │     │  │ Preserves order information
  │     │  └─ Output: Prime exponent vector
  │     │
  │     ├─ P-ADIC LIFT
  │     │  │ Convert exponents to residues (modular arithmetic)
  │     │  │ Apply to multiple primes simultaneously
  │     │  └─ Output: Multi-prime residue vectors
  │     │
  │     ├─ NTT FINGERPRINT
  │     │  │ Apply Number Theoretic Transform (like FFT, but in finite field)
  │     │  │ Compute spectrum over Galois field
  │     │  │ Captures frequency characteristics
  │     │  └─ Output: NTT coefficients (spectral fingerprint)
  │     │
  │     ├─ KAG GRID ANALYSIS
  │     │  │ Apply 8×8 additive predictor
  │     │  │ Measure how well chunk follows linear patterns
  │     │  │ Compute KAG separability metric
  │     │  └─ Output: KAG score (0-100)
  │     │
  │     ├─ PENROSE PATCH MAPPING
  │     │  │ Map chunk characteristics to Penrose tiling
  │     │  │ Use Genesis Mints as reference points:
  │     │  │  • Fine-structure constant (≈137.036)
  │     │  │  • Einstein field equation weights
  │     │  │  • Boltzmann entropy reference
  │     │  │ Calculate tile position and barycentric coords
  │     │  └─ Output: Tau vectors (5D coordinates on map)
  │     │
  │     └─ METRIC COMPUTATION
  │        ├─ Shannon entropy (bits/byte) → ideal ≈ 8
  │        ├─ Chi-squared statistic → vs uniform distribution
  │        ├─ Autocorrelation → detect repeating patterns
  │        ├─ Penrose match score → how well it fits tiling
  │        └─ KAG separability → linear predictability
  │
  ├─ AGGREGATION
  │  ├─ Compute statistics across all chunks:
  │  │  ├─ Mean entropy
  │  │  ├─ Std dev of key metrics
  │  │  └─ Chi-squared distribution fit
  │  │
  │  ├─ Z-SCORE ANOMALY DETECTION
  │  │  └─ Flag chunks where metrics deviate > ±3σ
  │  │     ├─ Low entropy (< 7 bits/byte)
  │  │     ├─ High chi-squared (poor randomness)
  │  │     ├─ High autocorrelation (patterns)
  │  │     └─ Low Penrose match (doesn't fit geometry)
  │  │
  │  └─ AGGREGATE TAU VECTORS
  │     └─ Average tau vectors across all chunks
  │        → Final artifact position on Penrose map
  │
  └─ FINAL SCORE CALCULATION
     │
     ├─ Entropy Component (30% weight)
     │  └─ Score = (mean_entropy / 8) × 100, capped at 100
     │
     ├─ Penrose Match Component (40% weight)
     │  └─ Score = mean_penrose_match × 100
     │
     ├─ Anomaly Component (30% weight)
     │  └─ Score = (1 - anomaly_fraction) × 100
     │
     ├─ Weighted Average
     │  └─ base_score = 0.3×entropy + 0.4×penrose + 0.3×anomaly
     │
     ├─ Bias Penalty (up to 25% reduction)
     │  │ Penalize suspicious patterns:
     │  │ ├─ All bytes identical
     │  │ ├─ Perfect repeating patterns
     │  │ ├─ Suspiciously high entropy (> 7.99 bits)
     │  │ └─ Very low entropy variance
     │  │
     │  └─ final_score = base_score × (1 - bias_penalty)
     │
     ├─ RISK LEVEL CLASSIFICATION
     │  ├─ If final_score < 70 → HIGH
     │  ├─ If 70 ≤ final_score < 90 → MEDIUM
     │  └─ If final_score ≥ 90 → LOW
     │
     └─ OUTPUT: AuditResult
        ├─ integrity_score: int (0-100)
        ├─ risk_level: str (LOW/MEDIUM/HIGH)
        ├─ tau_vectors: List[float] (5 values)
        ├─ manifold_hash: str
        ├─ tile_hash: str
        ├─ anomalies: List[AnomalyDetail]
        └─ metrics: DetailedMetrics

┌────────────────────────────────────────────────────────────────┐
│ STEP 4: ARTIFACT BLOCKCHAIN RECORDING                          │
└────────────────────────────────────────────────────────────────┘

  artifact_chain.py
  │
  ├─ Create new ArtifactBlock:
  │  ├─ index = next_index_in_chain
  │  ├─ artifact_hash = SHA-256(file_contents)
  │  ├─ tau_vectors = [result from RIM-OS]
  │  ├─ manifold_hash = [from RIM-OS]
  │  ├─ timestamp = now()
  │  └─ previous_hash = hash(last_block_in_chain)
  │
  ├─ Link to chain:
  │  └─ Block hash = SHA-256(block_data + previous_hash)
  │
  └─ Save to data/artifact_chain.json
     └─ (Persistent record of all artifact positions)

┌────────────────────────────────────────────────────────────────┐
│ STEP 5: REPORT GENERATION                                      │
└────────────────────────────────────────────────────────────────┘

  pdf_generator.py & svg_generator.py
  │
  ├─ PDF REPORT (pdf_generator.py)
  │  ├─ Header: File name, upload timestamp, upload_id
  │  ├─ Executive Summary: Risk level, integrity score
  │  ├─ KPI Section:
  │  │  ├─ Integrity Score (0-100)
  │  │  ├─ Risk Badge (visual indicator)
  │  │  ├─ Anomalies Found (count & details)
  │  │  └─ KAG Score, Coverage %, etc.
  │  ├─ Metrics Table: Entropy, chi-squared, correlation, etc.
  │  ├─ Anomaly Report: List of suspicious chunks with metrics
  │  ├─ Blockchain Section: Block hash, tau vectors, index
  │  ├─ Metadata: File hash, file size, processing time
  │  └─ Footer: RIMOS branding, timestamp
  │
  ├─ SVG VISUALIZATION (svg_generator.py)
  │  ├─ Render Penrose P3 tiling pattern
  │  ├─ Mark Genesis Mint positions
  │  ├─ Plot artifact position (tau_vectors on map)
  │  ├─ Show surrounding tiles with metadata
  │  └─ Add legend (colors for risk levels)
  │
  └─ HTML REPORT
     └─ Interactive version of PDF with links & expandable sections

┌────────────────────────────────────────────────────────────────┐
│ STEP 6: API RESPONSE TO FRONTEND                               │
└────────────────────────────────────────────────────────────────┘

  UploadResponse sent to frontend:
  {
    "upload_id": "550e8400-e29b-41d4-a716-446655440000",
    "file_name": "model_weights.safetensors",
    "file_size": 4294967296,
    "file_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "kpis": [
      {
        "label": "Integrity Score",
        "value": "87",
        "status": "good"
      },
      {
        "label": "Risk Level",
        "value": "MEDIUM",
        "status": "warning"
      },
      {
        "label": "Anomalies Found",
        "value": "3",
        "status": "neutral"
      }
    ],
    "verification": {
      "status": "verified",
      "confidence": 98.5,
      "checks": ["format_valid", "signature_ok", "size_ok"]
    },
    "artifact_block": {
      "index": 1042,
      "artifact_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
      "tau_vectors": [0.618, 1.618, 0.381, 0.236, 0.146],
      "manifold_hash": "xyz123abc456",
      "timestamp": "2026-03-18T14:30:00Z"
    },
    "message": "File processed successfully"
  }

┌────────────────────────────────────────────────────────────────┐
│ STEP 7: FRONTEND DISPLAYS RESULTS                              │
└────────────────────────────────────────────────────────────────┘

  React Components render:
  │
  ├─ KPIDisplay component
  │  └─ Shows integrity score (color-coded), risk level badge, anomalies
  │
  ├─ BlockchainInfo component
  │  └─ Shows tau vectors, artifact hash, block index
  │
  ├─ Report links (PDF/HTML/SVG downloads)
  │
  └─ MintFlow component (optional)
     └─ Option to mint NFT certificate on Solana

┌────────────────────────────────────────────────────────────────┐
│ STEP 8: OPTIONAL - NFT MINTING (Solana)                        │
└────────────────────────────────────────────────────────────────┘

  MintFlow component
  │
  ├─ User connects Solana wallet (Phantom/Solflare)
  │
  ├─ Frontend calls: POST /api/mint/prepare
  │  ├─ Backend prepares NFT metadata
  │  │  ├─ Name: "{file_name} Review Certificate"
  │  │  ├─ Description: "Integrity score: {score}, Risk: {level}"
  │  │  ├─ Image: SVG visualization of Penrose tiling
  │  │  ├─ Attributes: score, risk_level, tau_vectors, etc.
  │  │  └─ Upload to IPFS
  │  │
  │  └─ Returns: {ipfs_url, metadata_json}
  │
  ├─ Frontend calls: POST /api/mint/finalize with signed transaction
  │  ├─ Backend creates NFT using Metaplex on Solana Devnet
  │  ├─ Transaction signed by user's connected wallet
  │  └─ Returns: {nft_mint_address, transaction_signature}
  │
  └─ Display NFT URL to user
     └─ User can view on Solana blockchain explorer

```

### Key Mathematical Concepts

#### Gödel Encoding

Converts binary data (bytes) into a sequence of prime exponents.

- Byte value → exponent of corresponding prime in sequence
- Preserves order information
- Reversible process

#### p-adic Lift

Applies modular arithmetic to create numeric vectors from byte data.

- Converts exponents to residues modulo different primes
- Creates multi-dimensional vectors
- Captures local structure information

#### NTT (Number Theoretic Transform)

Like FFT but operates in finite field (Galois field).

- Computes spectrum of data in modular arithmetic
- Captures frequency characteristics without floating-point
- Deterministic and reproducible

#### KAG Grid

8×8 additive predictor for linear analysis.

- Tests how well data follows linear patterns
- Computes separability measure
- Helps identify highly ordered/suspicious data

#### Penrose Tiling

Aperiodic mathematical tiling of the plane.

- Uses 5D coordinates (tau_vectors)
- Genesis Mints provide orientation anchors
- Each artifact gets a unique position that can be verified mathematically

---

## API Reference

### Upload Endpoints

#### Single File Upload

```
POST /api/upload

Request:
  Content-Type: multipart/form-data
  Body:
    - file: Binary file (< 100 MB)

Response (202 Accepted):
  {
    "upload_id": "string (UUID)",
    "file_name": "string",
    "file_size": "number",
    "file_hash": "string (SHA-256)",
    "kpis": [ KPI objects ],
    "verification": { verification status },
    "artifact_block": { blockchain entry },
    "message": "string"
  }

Error Responses:
  400 - Invalid file type or too large
  413 - Request entity too large
  422 - Signature verification failed
```

#### Chunked Upload - Initiate

```
POST /api/upload/chunked/init

Request:
  Content-Type: application/json
  Body:
    {
      "file_name": "string",
      "file_size": "number"
    }

Response (200 OK):
  {
    "upload_id": "string (UUID)",
    "chunk_size": 20971520,
    "total_chunks": number,
    "message": "Upload session created"
  }
```

#### Chunked Upload - Upload Chunk

```
PUT /api/upload/chunked/{upload_id}/chunk/{chunk_index}

Request:
  Content-Type: application/octet-stream
  Body: Binary chunk data (20 MB max)

Response (200 OK):
  {
    "chunk_index": number,
    "uploaded_chunks": number,
    "remaining_chunks": number,
    "upload_id": "string"
  }

Error Responses:
  400 - Invalid chunk index or size
  404 - Upload session not found
  409 - Conflict (session expired or another client completed)
```

#### Chunked Upload - Get Status

```
GET /api/upload/chunked/{upload_id}/status

Response (200 OK):
  {
    "upload_id": "string",
    "uploaded_chunks": number,
    "total_chunks": number,
    "resumable_chunks": [ numbers ],
    "status": "in_progress" | "completed" | "expired",
    "created_at": "ISO timestamp",
    "expires_at": "ISO timestamp"
  }
```

#### Chunked Upload - Complete

```
POST /api/upload/chunked/{upload_id}/complete

Response (202 Accepted):
  {
    "upload_id": "string",
    "message": "Upload completed, processing started",
    "status_url": "/api/upload/{upload_id}/status"
  }

Poll for results using /api/report/{upload_id} endpoint after 5-10 seconds
```

### Report Endpoints

#### Get PDF Report

```
GET /api/report/{upload_id}/pdf

Response (200 OK):
  Content-Type: application/pdf
  Body: PDF file binary

Error: 404 if report not yet generated
```

#### Get HTML Report

```
GET /api/report/{upload_id}/html

Response (200 OK):
  Content-Type: text/html
  Body: HTML report

Error: 404 if report not yet generated
```

#### Get SVG Visualization

```
GET /api/report/{upload_id}/svg

Response (200 OK):
  Content-Type: image/svg+xml
  Body: SVG visualization of Penrose tiling with artifact position

Error: 404 if not yet generated
```

### NFT Minting Endpoints

#### Prepare Mint Metadata

```
POST /api/mint/prepare

Request:
  Content-Type: application/json
  Body:
    {
      "upload_id": "string",
      "creator_wallet": "string (Solana address)"
    }

Response (200 OK):
  {
    "ipfs_url": "https://ipfs.io/ipfs/{hash}",
    "metadata": { NFT metadata },
    "fee_estimate": number,
    "message": "Metadata prepared"
  }
```

#### Finalize Mint

```
POST /api/mint/finalize

Request:
  Content-Type: application/json
  Body:
    {
      "upload_id": "string",
      "transaction_signature": "string",
      "creator_wallet": "string"
    }

Response (200 OK):
  {
    "nft_mint_address": "string (Solana address)",
    "transaction_signature": "string",
    "explorer_url": "https://explorer.solana.com/address/{mint}",
    "message": "NFT minted successfully"
  }
```

---

## Development Workflow

### Setup Development Environment

#### Backend Setup

```bash
# Navigate to backend
cd backend

# Create Python virtual environment
python -m venv venv
source venv/Scripts/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn app.main:app --reload --port 8000

# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

#### Frontend Setup

```bash
# Navigate to frontend
cd web

# Install Node dependencies
npm install

# Run development server
npm run dev

# Frontend runs at http://localhost:3000
```

### Making Changes

#### Backend Changes

1. **Add new API endpoint:**
    - Create new router in `app/routers/`
    - Define Pydantic schemas in `app/models/`
    - Add service logic in `app/services/`
    - Mount router in `app/main.py`

2. **Modify RIM-OS audit logic:**
    - Edit `rim_os_v2.py`
    - Ensure mathematical determinism (same input → same output)
    - Test with existing audit cache files
    - Update tests in `tests/`

3. **Add new service:**
    - Create `app/services/new_service.py`
    - Define dependencies in `app/dependencies.py`
    - Inject into routers using FastAPI dependency system

#### Frontend Changes

1. **Add new component:**
    - Create `src/components/NewComponent.tsx`
    - Export from `src/components/index.ts`
    - Use in pages with proper TypeScript types

2. **Modify UI:**
    - Edit Tailwind CSS classes
    - Update Framer Motion animations
    - Test responsive design (mobile, tablet, desktop)

3. **Add API integration:**
    - Update `src/lib/api.ts` with new API calls
    - Use React hooks (`useEffect`, `useState`, custom hooks)
    - Add proper error handling and loading states

### Code Style Guidelines

**Backend (Python):**

- Follow PEP 8
- Type hints required for all functions
- Docstrings for all public functions
- Use descriptive variable names
- Max line length: 88 characters (Black formatter)

**Frontend (TypeScript):**

- Strict TypeScript mode
- Functional components with hooks
- Props interfaces for all components
- Descriptive component names (PascalCase)
- Utility functions in `src/lib/`

### Running Tests

**Backend:**

```bash
cd backend

# Run all tests
pytest

# Run specific test file
pytest tests/test_api_errors.py

# Run with coverage
pytest --cov=app tests/

# Run specific test
pytest tests/test_upload.py::test_single_upload
```

**Frontend:**

```bash
cd web

# Lint
npm run lint

# Type check
npm run type-check

# Build
npm run build
```

---

## Testing

### Backend Testing

**Test Structure:**

- Unit tests in `tests/test_*.py`
- Test fixtures in `tests/conftest.py`
- Mock objects for external services
- Integration tests for API endpoints

**Key test files:**

| File                             | Tests                             |
| -------------------------------- | --------------------------------- |
| `test_upload.py`                 | Single upload endpoint            |
| `test_chunked_upload_worker.py`  | Chunked upload functionality      |
| `test_signature_verification.py` | Ed25519 signature validation      |
| `test_pipeline.py`               | Full upload → audit → report flow |
| `test_rimos_integration.py`      | RIM-OS audit engine               |
| `test_metadata_parsing.py`       | Artifact metadata extraction      |
| `test_batch_upload.py`           | Multiple file uploads             |
| `test_api_errors.py`             | Error handling & status codes     |

**Running tests:**

```bash
cd backend

# Run all
pytest

# Run specific
pytest tests/test_pipeline.py -v

# With coverage
pytest --cov=app --cov-report=html tests/

# Watch mode (requires pytest-watch)
ptw
```

### Frontend Testing

**Recommended approach:**

- Component tests with React Testing Library
- Integration tests with Cypress/Playwright
- Type checking with TypeScript strict mode

---

## Troubleshooting

### Common Backend Issues

#### 1. **Upload Times Out**

**Problem:** Large file uploads hang or timeout
**Solution:**

- Check chunked upload is being used (> 100 MB)
- Verify each chunk is < 20 MB
- Ensure temp disk space available
- Check `chunked_upload_service.py` timeout settings

#### 2. **"Invalid file type" Error**

**Problem:** Supported file types rejected
**Solution:**

- Check extension in `SUPPORTED_FORMATS` in `file_validation.py`
- Verify file actually has claimed extension
- Check MIME type validation isn't too restrictive

#### 3. **RIM-OS Audit Fails**

**Problem:** `run_rim_audit()` returns error
**Solution:**

- Verify file is valid and readable
- Check disk space for temp 1 MB chunks
- Look at error message in logs
- Test with known-good file from `examples/`

#### 4. **Reports Not Generating**

**Problem:** PDF/SVG download returns 404
**Solution:**

- Wait 10-15 seconds after upload (RIM-OS is CPU-intensive)
- Check `data/report_cache/` for cached files
- Verify `pdf_generator.py` and `svg_generator.py` have no errors
- Check disk space for output files

#### 5. **Blockchain Chain Corrupted**

**Problem:** `artifact_chain.json` is invalid JSON
**Solution:**

- Backup current file
- Restore from backup if available
- Manually edit JSON and remove the problematic entry
- Verify chain hash linkage

### Common Frontend Issues

#### 1. **"Failed to connect to API"**

**Problem:** Frontend can't reach backend
**Solution:**

- Verify backend is running (`http://localhost:8000`)
- Check CORS settings in `app/main.py`
- Verify API base URL in `src/lib/api.ts` matches backend port
- Check browser console for specific error

#### 2. **Upload Progress Stuck**

**Problem:** Progress bar doesn't update
**Solution:**

- Check network tab in DevTools for chunk requests
- Verify chunks are being received by backend
- Check `ChunkedUploadService` is processing chunks
- Clear browser cache

#### 3. **Solana Wallet Won't Connect**

**Problem:** "Cannot connect wallet" error
**Solution:**

- Verify Phantom/Solflare wallet installed
- Check wallet is on Solana Devnet network
- Try different wallet from dropdown
- Check `WalletProvider.tsx` configuration

---

## Key Files Quick Reference

### Must-Know Files

| File                                                                                        | Purpose           |
| ------------------------------------------------------------------------------------------- | ----------------- |
| [app/main.py](../backend/app/main.py)                                                       | FastAPI app setup |
| [rim_os_v2.py](../backend/rim_os_v2.py)                                                     | Core audit engine |
| [app/routers/upload.py](../backend/app/routers/upload.py)                                   | Upload endpoint   |
| [app/services/chunked_upload_service.py](../backend/app/services/chunked_upload_service.py) | Upload management |
| [app/services/rim_wrapper.py](../backend/app/services/rim_wrapper.py)                       | RIM-OS wrapper    |
| [app/services/pdf_generator.py](../backend/app/services/pdf_generator.py)                   | Report generation |
| [app/services/artifact_chain.py](../backend/app/services/artifact_chain.py)                 | Blockchain ledger |
| [src/components/FileUpload.tsx](../web/src/components/FileUpload.tsx)                       | Upload UI         |
| [src/components/KPIDisplay.tsx](../web/src/components/KPIDisplay.tsx)                       | Results display   |
| [src/lib/api.ts](../web/src/lib/api.ts)                                                     | API client        |

### Configuration Files

| File                                                    | Purpose             |
| ------------------------------------------------------- | ------------------- |
| [backend/requirements.txt](../backend/requirements.txt) | Python dependencies |
| [web/package.json](../web/package.json)                 | Node dependencies   |
| [app/config.py](../backend/app/config.py)               | Backend settings    |
| [web/next.config.ts](../web/next.config.ts)             | Next.js settings    |

---

## Supporting Documentation

- [README.md](../README.md) - Project overview
- [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md) - Simple developer guide
- [MILESTONE_2_CLIENT_REPORT.md](./MILESTONE_2_CLIENT_REPORT.md) - Project status

---

## Contact & Support

For questions or issues:

1. Check this documentation first
2. Review test files for usage examples
3. Check error logs in `backend/logs/`
4. Review existing issue discussions

---

**Last Updated:** March 18, 2026
**Version:** 1.0
**Status:** Complete
