# RIMOS - Quick Reference Guide

> Fast lookup guide for common tasks and key information

---

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Frontend

```bash
cd web
npm install
npm run dev
# Web: http://localhost:3000
```

### Run Tests

```bash
cd backend
pytest                    # All tests
pytest -v tests/test_pipeline.py  # Specific
```

---

## Project Structure At a Glance

```
backend/
  app/
    routers/          ← API endpoints (upload, mint, report)
    services/         ← Business logic (audit, validation, generation)
    models/           ← Pydantic data schemas
    main.py           ← FastAPI app setup
  rim_os_v2.py        ← Core audit engine (DON'T MODIFY without testing!)
  tests/              ← Test suite

web/
  src/
    app/              ← Pages (landing, upload, report)
    components/       ← React components (FileUpload, KPIDisplay, etc.)
    lib/              ← Utilities (api.ts, solana.ts)
```

---

## Core Pipeline (5 Steps)

```
1. FILE UPLOAD      → Backend receives file (single or chunked)
2. VALIDATION       → Check type, size, signature
3. RIM-OS AUDIT     → Math pipeline (Gödel → p-adic → NTT → KAG → Penrose)
4. BLOCKCHAIN       → Record artifact position in chain
5. RESPONSE & UI    → Frontend displays KPIs, blockchain info, reports
```

---

## Key Services Quick Lookup

| Service                       | What It Does                         | File        |
| ----------------------------- | ------------------------------------ | ----------- |
| **rim_wrapper.py**            | Calls RIM-OS audit engine            | `services/` |
| **chunked_upload_service.py** | Manages 20MB chunk upload sessions   | `services/` |
| **file_validation.py**        | Validates file type/size/signature   | `services/` |
| **pdf_generator.py**          | Creates downloadable reports         | `services/` |
| **svg_generator.py**          | Renders Penrose tiling visualization | `services/` |
| **artifact_chain.py**         | Maintains blockchain ledger          | `services/` |
| **ipfs_service.py**           | Prepares NFT metadata for IPFS       | `services/` |

---

## API Endpoints Cheat Sheet

### Upload

```
POST   /api/upload                          Single file (< 100 MB)
POST   /api/upload/chunked/init             Start chunked session
PUT    /api/upload/chunked/{id}/chunk/{i}   Upload 20 MB chunk
GET    /api/upload/chunked/{id}/status      Check progress
POST   /api/upload/chunked/{id}/complete    Finish & process
```

### Reports

```
GET    /api/report/{id}/pdf                 Download audit PDF
GET    /api/report/{id}/html                View HTML report
GET    /api/report/{id}/svg                 Get Penrose visualization
```

### NFT Minting

```
POST   /api/mint/prepare                    Prepare metadata
POST   /api/mint/finalize                   Create NFT on Solana
```

---

## Data Model Reference

### Upload Response

```json
{
  "upload_id": "UUID",
  "file_name": "string",
  "file_hash": "SHA-256",
  "integrity_score": 0-100,
  "risk_level": "LOW|MEDIUM|HIGH",
  "kpis": [ {label, value, status} ],
  "artifact_block": {
    "index": int,
    "tau_vectors": [5 floats],
    "artifact_hash": "SHA-256"
  }
}
```

### Artifact Block (Blockchain Entry)

```json
{
    "index": 1,
    "artifact_hash": "SHA-256 of file",
    "tau_vectors": [0.618, 1.618, 0.381, 0.236, 0.146],
    "manifold_hash": "position_hash",
    "timestamp": "ISO-8601",
    "previous_hash": "SHA-256"
}
```

---

## Frontend Components Quick Reference

| Component        | Purpose                   | Props                         |
| ---------------- | ------------------------- | ----------------------------- |
| `FileUpload`     | Drag-drop file selector   | `onUploadComplete`, `onError` |
| `KPIDisplay`     | Show audit results grid   | `kpis`, `riskLevel`, `score`  |
| `BlockchainInfo` | Display artifact position | `artifactBlock`               |
| `MintFlow`       | NFT minting wizard        | `uploadId`, `onMintComplete`  |
| `WalletProvider` | Solana wallet setup       | `children`                    |

---

## Common Development Tasks

### Add New API Endpoint

1. Create router in `app/routers/new_router.py`
2. Define schemas in `app/models/schemas.py`
3. Implement service in `app/services/`
4. Mount in `app/main.py`: `app.include_router(router)`

### Modify Audit Logic

1. Edit `rim_os_v2.py`
2. **MUST preserve determinism** (same input → same output)
3. Add tests to `tests/test_rimos_integration.py`
4. Test with existing files from `data/report_cache/`

### Add Frontend Component

1. Create `src/components/NewComponent.tsx`
2. Define TypeScript interface for props
3. Export from component index
4. Use in pages with proper error handling

### Fix Upload Issues

1. Check `file_validation.py` for type/size restrictions
2. Verify `chunked_upload_service.py` for session management
3. Look at `worker_executor.py` for background job handling

---

## Debugging Commands

### Backend Logs

```bash
# Watch logs in real-time
tail -f backend/logs/app.log

# Search for error
grep ERROR backend/logs/app.log

# Find specific upload_id
grep "550e8400-e29b-41d4-a716" backend/logs/app.log
```

### Database/Cache

```bash
# View blockchain chain
cat backend/data/artifact_chain.json | python -m json.tool

# View cached report
cat backend/data/report_cache/{upload_id}.json | python -m json.tool

# List temp upload files
ls -la backend/data/temp_uploads/
```

### API Testing

```bash
# Using curl
curl -X POST http://localhost:8000/api/upload/chunked/init \
  -H "Content-Type: application/json" \
  -d '{"file_name":"test.bin","file_size":1000000}'

# Using Python
python -c "
import requests
r = requests.post('http://localhost:8000/api/upload/chunked/init',
                  json={'file_name': 'test.bin', 'file_size': 1000000})
print(r.json())
"
```

---

## File Type Support

**Supported Model Formats:**

- `.lm3z` - LM3Z format
- `.rim0`, `.rim95` - RIMOS formats
- `.safetensors` - HuggingFace safe format
- `.bin`, `.ckpt` - Binary checkpoints
- `.pt`, `.pth` - PyTorch weights
- `.gguf` - GGML uniform format
- `.onnx` - ONNX runtime format

**Limits:**

- Min size: 1 KB
- Max size: 10 GB
- Chunk size: 20 MB (chunked upload)
- Single upload max: 100 MB

---

## Environment Variables

**Backend** (`backend/app/config.py`):

```
CHUNK_SIZE=20971520         # 20 MB chunks
MAX_FILE_SIZE=10737418240   # 10 GB max
UPLOAD_DIR=backend/data/uploads/
TEMP_DIR=backend/data/temp_uploads/
REPORT_CACHE_DIR=backend/data/report_cache/
```

**Frontend** (`web/.env.local`):

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SOLANA_NETWORK=devnet
```

---

## Risk Score Ranges

| Score Range | Risk Level | Color     |
| ----------- | ---------- | --------- |
| 0-69        | HIGH       | 🔴 Red    |
| 70-89       | MEDIUM     | 🟡 Yellow |
| 90-100      | LOW        | 🟢 Green  |

**Factors affecting score (Weighted):**

- 30% Entropy (ideal ≈ 8 bits/byte)
- 40% Penrose Match (fit to tiling)
- 30% Anomaly Detection (fewer anomalies = better)

---

## Testing Checklist

Before committing:

```
Backend:
  ☐ All tests pass: pytest
  ☐ Type hints on all functions
  ☐ Docstrings for public APIs
  ☐ No print() statements (use logging)

Frontend:
  ☐ npm run lint passes
  ☐ npm run type-check passes
  ☐ npm run build succeeds
  ☐ Components render without errors

General:
  ☐ Tested with both upload methods (single & chunked)
  ☐ Tested error cases
  ☐ API endpoints documented
```

---

## Common Error Fixes

| Error                                           | Cause                          | Fix                                                |
| ----------------------------------------------- | ------------------------------ | -------------------------------------------------- |
| `ValidationError: file extension not supported` | File type not in whitelist     | Add to `SUPPORTED_FORMATS` in `file_validation.py` |
| `ChunkedUploadService: Session not found`       | Session expired or wrong ID    | Restart upload from beginning                      |
| `Cannot connect to API`                         | Backend not running            | Run `uvicorn app.main:app --reload`                |
| `PDF generation failed`                         | Disk space or permission       | Check `/data/report_cache/` permissions            |
| `Wallet connection failed`                      | Wrong network or wallet        | Switch wallet to Solana Devnet                     |
| `RIM-OS audit timeout` (> 10 min)               | Very large file or slow system | File is normal, wait or reduce size                |

---

## Key Mathematical Constants

| Concept                 | Value         | Purpose                |
| ----------------------- | ------------- | ---------------------- |
| Fine-structure constant | ≈ 137.036     | Genesis Mint reference |
| Ideal entropy           | ≈ 8 bits/byte | Randomness benchmark   |
| Z-score threshold       | ±3σ           | Anomaly detection      |
| NTT field modulus       | Prime number  | FFT in finite field    |
| Golden ratio (φ)        | ≈ 1.618       | Penrose geometry       |

---

## Performance Tips

**Backend:**

- RIM-OS audit on 1 GB file ≈ 30-60 seconds
- Use chunked upload for files > 100 MB
- Reports cache in `data/report_cache/`
- Monitor disk space for temp files

**Frontend:**

- Images optimized with Next.js Image component
- SVG rendering can be slow with large tilings (> 5 MB)
- Client-side wallet signing prevents server exposure

---

## Documentation Map

| Document                                                               | Purpose                                           |
| ---------------------------------------------------------------------- | ------------------------------------------------- |
| [COMPREHENSIVE_DEVELOPER_GUIDE.md](./COMPREHENSIVE_DEVELOPER_GUIDE.md) | **Read first** - Complete architecture & pipeline |
| [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)                             | Simple overview for new developers                |
| [README.md](../README.md)                                              | Project introduction                              |
| [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)                             | This file - Quick lookup                          |

---

**Last Updated:** March 18, 2026
**Use case:** During development, debugging, deployment
