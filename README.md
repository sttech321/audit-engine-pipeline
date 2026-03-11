# Pass97

Cryptographic audit verification and optional NFT minting for audit artifacts.

Pass97 is a full-stack application that accepts binary artifacts, runs them through the RIM-OS v2 audit pipeline, returns a deterministic integrity report, and can prepare NFT metadata for Solana-based provenance workflows.

## Overview

The project is split into two apps:

- `backend/`: FastAPI API for uploads, audit execution, report generation, and mint metadata preparation
- `web/`: Next.js frontend for upload, progress tracking, report viewing, and wallet-based mint flow

Core behavior:

- Same file produces the same SHA-256 hash and the same audit result
- PASS97-native formats (`.lm3z`, `.rim0`, `.rim95`) get full verification messaging
- Other file types can still be uploaded and receive a limited analysis response
- Raw model data is not stored as application state; the system computes fingerprints, metrics, and generated reports

## Main Flow

```text
Upload file -> validate + hash -> RIM-OS v2 audit -> report artifacts -> optional NFT metadata prep
```

What the user sees:

1. Upload a file from the web UI.
2. Files under 100 MB use standard multipart upload.
3. Files at or above 100 MB use resumable chunked upload with parallel chunk transfer.
4. The backend runs the RIM-OS v2 audit and returns KPIs, verification status, and file hash.
5. The user can open the generated report or prepare mint metadata for a Solana NFT flow.

## Features

- Deterministic SHA-256 file fingerprinting
- RIM-OS v2 audit pipeline with integrity score, anomaly count, KAG score, and risk classification
- Single-file upload and batch upload endpoints
- Chunked upload for large files with progress polling and resumability
- Structured metadata parsing and optional Ed25519 signature verification
- PDF, HTML, and Penrose SVG report generation
- Abuse protection features including rate limiting, deduplication, and replay detection
- Solana wallet frontend flow with backend mint metadata preparation

## Repository Layout

```text
pass97/
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- routers/
|   |   |-- services/
|   |   `-- models/
|   |-- tests/
|   |-- requirements.txt
|   `-- rim_os_v2.py
|-- web/
|   |-- src/
|   |   |-- app/
|   |   `-- components/
|   |-- package.json
|   `-- README.md
|-- shared/
|   `-- types.ts
`-- docs/
    `-- DEVELOPER_GUIDE.md
```

## Backend API

Primary routes exposed by the FastAPI app:

- `GET /`: health-style root message
- `POST /api/upload`: single-file upload and audit
- `POST /api/upload/batch`: batch upload
- `POST /api/upload/chunked/init`: create chunked upload session
- `PUT /api/upload/chunked/{upload_id}/chunk/{chunk_index}`: upload a chunk
- `GET /api/upload/chunked/{upload_id}/status`: poll chunked upload status
- `POST /api/upload/chunked/{upload_id}/complete`: finalize chunked upload and start processing
- `GET /api/report/{upload_id}/html`: rendered report
- `GET /api/report/{upload_id}/pdf`: PDF report
- `GET /api/report/{upload_id}/svg`: Penrose SVG
- `POST /api/mint/prepare`: prepare deterministic NFT metadata payload
- `POST /api/mint/finalize`: finalize mint bookkeeping

## Local Setup

### Prerequisites

- Python 3.11+ recommended
- Node.js 20+ recommended
- npm

### 1. Start the backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Backend will be available at `http://localhost:8000`.

### 2. Start the frontend

```powershell
cd web
npm install
@"
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MAX_FILE_SIZE_BYTES=10000000000
"@ > .env.local
npm run dev
```

Frontend will be available at `http://localhost:3000`.

## Configuration Notes

Important backend defaults from `backend/app/config.py`:

- `max_file_size`: `10_000_000_000` bytes
- `chunk_size_bytes`: `20 MB`
- `chunk_upload_max_concurrent`: `8`
- `enable_rate_limiting`: enabled by default
- `enable_deduplication`: enabled by default
- `parse_metadata`: enabled by default
- `verify_signatures`: enabled by default

Important frontend behavior from `web/src/app/upload/page.tsx`:

- Files `>= 100 MB` switch to chunked upload
- API base URL comes from `NEXT_PUBLIC_API_URL`
- Frontend max file size display comes from `NEXT_PUBLIC_MAX_FILE_SIZE_BYTES`

## Supported Artifact Handling

PASS97-native artifact formats:

- `.lm3z`
- `.rim0`
- `.rim95`

Current behavior:

- Native formats are labeled as full PASS97 audit mode
- Non-native formats are still accepted and return a structured response with limited-analysis messaging

## Reports and Outputs

Each successful upload can produce:

- Verification KPIs
- Verification status and confidence
- SHA-256 file hash
- Cached report data keyed by `uploadId`
- HTML report view
- PDF report download
- Penrose SVG visualization

## Testing

Backend tests are located under `backend/tests/`.

Typical test commands:

```powershell
cd backend
pytest
```

There is currently no project-level root script that runs both frontend and backend checks together.

## Tech Stack

- Frontend: Next.js 16, React 19, TypeScript, Axios, Solana wallet adapter
- Backend: FastAPI, Pydantic, Uvicorn, PyNaCl, SlowAPI, fpdf2
- Audit engine: `backend/rim_os_v2.py`
- Blockchain-related flow: Solana + NFT metadata preparation

## Developer Docs

For implementation details, read:

- [Developer Guide](docs/DEVELOPER_GUIDE.md)
- [Backend chunked upload example](backend/examples/CHUNKED_UPLOAD_README.md)
- [Frontend app notes](web/README.md)
