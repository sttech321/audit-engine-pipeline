# Milestone 4 Docs Consistency Fixes (March 23, 2026)

This addendum aligns documentation with the current codebase and supersedes older examples where fields differ.

## API Docs Access

- Swagger/OpenAPI UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Canonical API Contracts

### Upload (`POST /api/upload`)

- Uses camelCase: `uploadId`, `fileHash`, `artifactBlock`, `fileInfo`.
- Schema source: `backend/app/models/upload_schemas.py` (`UploadResponse`).

### Chunked Upload (`/api/upload/chunked/*`)

- Uses snake_case: `upload_id`, `uploaded_chunks`, etc.
- Init request shape:
  - `filename`
  - `total_size`
  - `total_chunks`
  - `chunk_size`
- Schema source: `backend/app/models/chunked_upload_schemas.py`.

### IPFS + Mint Flow

1. `POST /api/ipfs/upload`
   - Request: `uploadId`, `fileHash`, `metadata`, optional `auditData`
   - Response: `url`, `cid`, `provider`, `fallbackUsed`
2. `POST /api/mint/prepare`
   - Request: `uploadId`, `walletAddress`, `fileHash`, `metadata`, optional `metadataUrl`, optional `auditData`
   - Response: `metadata{url,provider,fallbackUsed}`, `mintHash`, `nftMetadata`
3. `POST /api/mint/finalize`
   - Request: `mintAddress`, `uploadId`, `signature`
   - Response: `success`, `message`

Source files:
- `backend/app/routers/ipfs.py`
- `backend/app/routers/mint.py`
- `backend/app/models/mint_schemas.py`

## Frontend Route + Props Corrections

- Report page route is dynamic:
  - `web/src/app/report/[uploadId]/page.tsx`
- `MintFlow` prop shape:
  - `uploadData: UploadResponse`
- `BlockchainInfo` prop shape:
  - `block?: ArtifactBlock | null`
  - `chainHeight?: number`

Source files:
- `web/src/app/report/[uploadId]/page.tsx`
- `web/src/components/MintFlow.tsx`
- `web/src/components/BlockchainInfo.tsx`

## Environment Variable Clarifications

- `NEXT_PUBLIC_ENABLE_NFT` controls whether mint UI is shown on upload page.
- `NEXT_PUBLIC_SOLANA_NETWORK` is documented for forward compatibility; wallet provider currently hardcodes Devnet.
- Backend `app/config.py` does not consume `SOLANA_RPC_URL` / `SOLANA_NETWORK`.

Source files:
- `web/src/app/upload/page.tsx`
- `web/src/components/WalletProvider.tsx`
- `backend/app/config.py`

## EU AI Act Layer Coverage

The EU layer is active and should be documented as a first-class backend module:

- Module: `backend/eu_ai_act_layer.py`
- Attached report fields:
  - `EU_AI_ACT_FULL`
  - `EU_AI_ACT_HASH`
- Visible in report UI via `/api/report/{upload_id}/extended`

## Penrose Visualization Clarification

The current SVG endpoint now renders a chain-anchored viewport:

- Global tiling seed from artifact chain state
- Marker rendered as artifact position in global manifold
- Endpoints: `/api/report/{upload_id}/svg`, HTML report rendering path

Source files:
- `backend/app/services/svg_generator.py`
- `backend/app/routers/report.py`

## Notes

- When older examples conflict with this file, use this file and model/schema files as source of truth.
- PDF generation currently does not embed Penrose SVG in the `fpdf2` output path (known limitation).
