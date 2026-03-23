# RIMOS - Developer Guide

> A simple explanation of how this project works, for developers.

---

## What Is This Project?

**RIMOS** is a system that **reviews binary files** (like AI model weights: `.lm3z`, `.rim0`, `.rim95`) and produces:

1. **Integrity score** (0–100)
2. **Risk level** (LOW / MEDIUM / HIGH)
3. **Anomaly report** (which chunks look suspicious)
4. **Verification status** (verified / verified with warnings / failed)

It does **not** store or reconstruct your data. It only computes cryptographic fingerprints and math-based metrics to assess file integrity.

---

## High-Level Flow (User Perspective)

```
User uploads file → Backend processes it → Returns review (KPIs, hash, risk) → User can mint NFT
```

---

## Backend Architecture (Simple View)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend  │────▶│   FastAPI Backend │────▶│  RIM-OS v2      │
│   (Next.js) │     │   (app/)          │     │  (rim_os_v2.py) │
└─────────────┘     └──────────────────┘     └─────────────────┘
                            │
                            ▼
                    ┌──────────────────┐
                    │  PDF / SVG       │
                    │  Report Gen      │
                    └──────────────────┘
```

---

## How Does the Review Get Generated?

### Step 1: File Upload

- **Small files (< 100 MB)**: Single `POST /api/upload`
- **Large files (≥ 100 MB)**: Chunked upload
  - `POST /api/upload/chunked/init` → get `upload_id`
  - `PUT /api/upload/chunked/{id}/chunk/{i}` → upload chunks (20 MB each, 8 parallel)
  - `POST /api/upload/chunked/{id}/complete` → start processing

### Step 2: RIM-OS Audit (the “review engine”)

All the math happens in **`rim_os_v2.py`**. The backend calls `run_rim_audit(file_path)` which wraps `audit_file()`.

**What RIM-OS does:**

1. **Split file into chunks** (1 MB each)
2. **For each chunk**, run a pipeline:

   ```
   Binary Chunk
      → Gödel encoding    (bytes → prime exponents, preserves order)
      → p-adic lift       (exponents → residues mod primes)
      → NTT fingerprint   (spectrum over a finite field)
      → KAG grid          (8×8 additive predictor)
      → Penrose patch     (P3 tiling geometry)
   ```

3. **Compute metrics per chunk**:
   - Shannon entropy
   - Chi‑squared vs uniform
   - Autocorrelation
   - Penrose match score
   - KAG separability

4. **Detect anomalies**: Chunks with z‑score > ±3σ on key metrics (low entropy, high chi2, etc.)

5. **Compute final score (0–100)**:
   - 30% entropy (≈8 bits is ideal)
   - 40% Penrose match
   - 30% anomaly fraction (fewer anomalies = better)
   - Bias penalty (up to 25% reduction for suspicious patterns)

6. **Risk level**:
   - Score < 70 → HIGH
   - 70 ≤ score < 90 → MEDIUM
   - Score ≥ 90 → LOW

### Step 3: Response Built From Report

The backend reads the RIM-OS report and builds:

- **KPIs**: Audit score, issues found, KAG score, coverage, Penrose sector
- **Verification**: Status, confidence %, pipeline checks
- **File hash**: SHA-256
- **Metadata**: Optional signature verification, artifact format

### Step 4: Report Outputs

- **PDF**: `GET /api/report/{upload_id}/pdf`
- **HTML**: `GET /api/report/{upload_id}/html`
- **Penrose SVG**: `GET /api/report/{upload_id}/svg`

### Step 5: Optional NFT Flow

- `POST /api/ipfs/upload` → metadata storage/preparation
- `POST /api/mint/prepare` → deterministic mint context (`mintHash`, `nftMetadata`)
- `POST /api/mint/finalize` → persist finalized mint reference

---

## Main Backend Files

| File / Folder         | Role |
|-----------------------|------|
| `app/main.py`         | FastAPI app, CORS, routers |
| `app/routers/upload.py`| Single-file upload + validation |
| `app/routers/chunked_upload.py` | Chunked upload init, chunk, status, complete |
| `app/services/chunked_upload_service.py` | Session, disk writes, RIM-OS trigger |
| `app/services/rim_wrapper.py` | Thin wrapper around RIM-OS `audit_file` |
| `app/routers/report.py` | PDF, HTML, SVG generation |
| `app/services/pdf_generator.py` | PDF report generation |
| `app/services/svg_generator.py` | Penrose SVG visualization |
| `rim_os_v2.py`        | Core audit engine: math pipeline, scoring, ledger |

---

## Data Flow (Technical)

```
File (bytes)
    │
    ├─ Small: read_file_streaming() → tmp file → run_rim_audit(path)
    │
    └─ Large: chunked upload
           │
           ├─ init → create session, pre-allocate file
           ├─ PUT chunk/i → write at offset (parallel, per-chunk locks)
           ├─ complete → start background task
           │      └─ run_rim_audit(path, progress_callback)
           │             └─ audit_file() in rim_os_v2
           │                    └─ for each 1MB chunk: process_chunk()
           │                           Gödel → p-adic → NTT → KAG → Penrose
           │                    └─ detect_anomalies()
           │                    └─ integrity_score()
           │                    └─ risk_level()
           │                    └─ build_ledger()
           └─ poll GET /status → processing_pct → result when done
```

---

## Core Concepts

### Genesis

Fixed anchors from physical constants (Standard Model, GR, thermodynamics). They define the coordinate frame. **Do not change** — it would break consistency.

### Gödel Encoding

Maps bytes to prime exponents. Same data → same encoding. Different byte order → different encoding. Used to get deterministic fingerprints.

### Penrose P3

Each chunk is mapped to a Penrose tiling region. The “match score” measures how well the chunk’s geometry fits expected patterns.

### Ledger

Each audit produces `next_state_hash`. Store it and pass as `prev_state` in the next audit for a chain-able ledger.

---

## Configuration (`app/config.py`)

- `max_file_size`: 10 GB default  
- `chunk_size_bytes`: 20 MB for chunked upload  
- `chunk_upload_max_concurrent`: 8 parallel chunk uploads  
- `validate_file_extension`, `parse_metadata`, `verify_signatures`: feature flags  

---

## Quick Start for New Developers

1. **Understand the flow**: Upload → RIM-OS audit → KPIs + hash + risk.
2. **Key entry point**: `run_rim_audit()` in `rim_wrapper.py` → `audit_file()` in `rim_os_v2.py`.
3. **Per-chunk pipeline**: `process_chunk()` in `rim_os_v2.py` (Gödel → p-adic → NTT → KAG → Penrose).
4. **Scoring**: `integrity_score()` and `risk_level()` in `rim_os_v2.py`.
5. **Reports**: PDF/HTML/SVG use cached results from `report.py` and `pdf_generator` / `svg_generator`.

---

## Glossary

| Term        | Meaning |
|------------|---------|
| **Chunk**  | 1 MB block of file (RIM-OS) or 20 MB block (upload) |
| **KAG**    | 8×8 additive predictor on NTT magnitudes |
| **NTT**    | Number-theoretic transform (FFT over finite field) |
| **Penrose**| P3 tiling geometry for deterministic positioning |
| **RIM-OS** | Audit engine (Gödel, p-adic, NTT, KAG, Penrose) |
| **Genesis**| Fixed anchors defining the coordinate system |
