# Pass97

**Cryptographic audit verification and NFT minting for AI model artifacts.**

Upload binary audit files, get a deterministic integrity score, and mint NFTs on Solana to prove provenance—without storing or reconstructing your data.

---

## What Is Pass97?

Pass97 is a system that:

1. **Reviews** your audit artifacts (`.lm3z`, `.rim0`, `.rim95`)
2. **Returns** an integrity score (0–100), risk level, and verification status
3. **Lets you mint** an NFT on Solana as proof of audit

**Key point:** We never store your model weights or raw data. We only compute cryptographic fingerprints and produce a report.

---

## How It Works (Simple Flow)

```
Upload file → RIM-OS v2 audits it → You get score + hash + risk → Optional: mint NFT
```

| Step | What happens |
|------|--------------|
| **1. Upload** | Drag and drop your file. Small files upload in one go; large files (100+ MB) use parallel chunked upload with progress. |
| **2. Audit** | RIM-OS v2 processes the file in chunks. You see real-time progress: upload %, then processing %. |
| **3. Results** | Integrity score, risk (LOW / MEDIUM / HIGH), anomaly count, KAG score, SHA-256 hash. |
| **4. Mint (optional)** | Connect a Solana wallet and mint an NFT that proves your audit passed. Metadata on IPFS; hash on-chain. |

---

## What You Get

- **Integrity score** (0–100) from the RIM-OS v2 pipeline
- **Risk level**: LOW, MEDIUM, or HIGH
- **Anomaly report**: which chunks (if any) look suspicious
- **SHA-256 hash** for deterministic verification
- **PDF report** and **Penrose SVG** visualization
- **Optional NFT** on Solana (Devnet) proving audit provenance

---

## Project Structure

```
pass97/
├── backend/          # FastAPI + RIM-OS v2 audit engine
├── web/              # Next.js frontend (upload, KPIs, mint)
├── shared/           # Shared types (e.g. UploadResponse)
├── docs/             # Developer guide and specs
└── README.md
```

---

## Quick Start

### 1. Start the backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Start the frontend

```bash
cd web
npm install
npm run dev
```

### 3. Open

- Frontend: http://localhost:3000  
- Backend API: http://localhost:8000  

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `web/.env.local` if the default differs.

---

## Core Principles

| ✓ We do | ✗ We don't |
|---------|------------|
| Deterministic verification (same file → same result) | Store model weights |
| Return hashes and metadata only | Run AI inference |
| NFTs prove audit integrity | Store raw data |
| Process and discard uploaded files | Reconstruct your model |

---

## Supported Formats

- `.lm3z`
- `.rim0`
- `.rim95`

---

## For Developers

See [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for:

- RIM-OS v2 pipeline (Gödel, p-adic, NTT, KAG, Penrose)
- API endpoints and data flow
- Configuration and glossary

---

## Tech Stack

- **Frontend:** Next.js, React, Solana Wallet Adapter, Tailwind
- **Backend:** FastAPI, RIM-OS v2 (Python)
- **Blockchain:** Solana (Devnet), Metaplex, IPFS (Irys)
