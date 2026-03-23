# RIMOS - API Integration Guide

> Complete guide for integrating with RIMOS APIs

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Upload APIs](#upload-apis)
- [Report APIs](#report-apis)
- [NFT Minting APIs](#nft-minting-apis)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)
- [Webhooks & Polling](#webhooks--polling)

---

## Overview

### Base URL

```
Development: http://localhost:8000
Production: [To be configured]
```

### Interactive API Documentation

- Swagger/OpenAPI UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### API Format

- **Protocol:** HTTP/REST
- **Request format:** JSON (with multipart for file uploads)
- **Response format:** JSON
- **Async support:** All operations are async-ready

### Naming Notes

- `POST /api/upload` returns camelCase keys: `uploadId`, `fileHash`, `artifactBlock`.
- Chunked endpoints use snake_case keys: `upload_id`, `uploaded_chunks`, etc.
- Extended report payload (`/api/report/{upload_id}/extended`) uses snake_case model fields.

### Rate Limiting

- 100 requests per minute per IP
- Large file uploads count as 1 request regardless of chunks
- Implemented via `slowapi` in `app/services/abuse_protection.py`

---

## Authentication

### Current Implementation

**RIMOS currently supports:**

- Public endpoints (no API key required for uploads)
- Optional Ed25519 signature verification for authenticated uploads
- Solana wallet signature for NFT minting

### Future Enhancements (Consider)

- API key authentication
- OAuth2 for persistent sessions
- Rate limiting per API key

### Optional Signature Verification

If providing authenticated upload:

```python
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder

# Generate keypair (done once)
signing_key = SigningKey.generate()
verify_key = signing_key.verify_key

# Sign message
message = b"artifact_binary_data"
signed = signing_key.sign(message).signature.hex()

# Submit with upload
# Include "X-Signature: {signed_hex}" header or in multipart
```

---

## Upload APIs

### 1. Single File Upload (< 100 MB)

**Endpoint:**

```
POST /api/upload
```

**Use When:**

- File size < 100 MB
- Quick upload needed
- No resumability required

**Request:**

```http
POST /api/upload HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data

file: <binary file data>
```

**Python Example:**

```python
import requests

file_path = "model_weights.safetensors"
with open(file_path, 'rb') as f:
    files = {'file': f}
    response = requests.post(
        'http://localhost:8000/api/upload',
        files=files
    )

result = response.json()
print(f"Upload ID: {result['uploadId']}")
print(f"Integrity Score: {result['kpis']}")
print(f"Risk Level: {result['artifactBlock']['manifold_hash']}")
```

**JavaScript/TypeScript Example:**

```typescript
async function uploadFile(file: File): Promise<string> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/upload`,
        {
            method: 'POST',
            body: formData,
        },
    );

    const result = await response.json();
    return result.uploadId;
}
```

**Response (200 OK):**

```json
{
    "uploadId": "550e8400-e29b-41d4-a716-446655440000",
    "fileInfo": {
        "name": "model_weights.safetensors",
        "size": 4294967296,
        "type": "application/octet-stream"
    },
    "fileHash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "kpis": [
        {
            "id": "kpi-1",
            "label": "Integrity Score",
            "value": "87",
            "status": "good",
            "trend": "stable"
        },
        {
            "id": "kpi-2",
            "label": "Risk Level",
            "value": "MEDIUM",
            "status": "warning",
            "trend": "down"
        },
        {
            "id": "kpi-3",
            "label": "Anomalies Found",
            "value": "3",
            "status": "warning",
            "trend": "up"
        }
    ],
    "verification": {
        "status": "Verified with Warnings",
        "confidence": 87,
        "timestamp": "2026-03-18T14:30:00Z",
        "checks": ["Stage 1 - Schema & Genesis: OK"]
    },
    "artifactBlock": {
        "index": 1042,
        "artifact_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        "tau_vectors": [0.618, 1.618, 0.381, 0.236, 0.146],
        "manifold_hash": "xyz123abc456def789",
        "tile_hash": "abc123def456",
        "timestamp": "2026-03-18T14:30:00Z",
        "barycentric": [0.33, 0.33, 0.34]
    },
    "metadata": {
        "verification_mode": "full"
    }
}
```

**Error Responses:**

```json
// 400 - Invalid file type
{
  "detail": "File type .exe not supported. Supported: .safetensors, .bin, .gguf, ..."
}

// 413 - File too large
{
  "detail": "File size 15GB exceeds maximum 10GB"
}

// 422 - Signature verification failed
{
  "detail": "Signature verification failed: Invalid Ed25519 signature"
}
```

---

### 2. Chunked Upload (> 100 MB)

**Use When:**

- File size ≥ 100 MB
- Need resumable uploads
- Parallel chunk processing
- Want to show upload progress

**Step 1: Initialize Session**

**Endpoint:**

```
POST /api/upload/chunked/init
```

**Request:**

```json
{
    "filename": "large_model.safetensors",
    "total_size": 5368709120,
    "total_chunks": 256,
    "chunk_size": 20971520
}
```

**Python Example:**

```python
import requests

response = requests.post(
    'http://localhost:8000/api/upload/chunked/init',
    json={
        'filename': 'large_model.safetensors',
        'total_size': 5368709120,
        'total_chunks': 256,
        'chunk_size': 20 * 1024 * 1024
    }
)

session = response.json()
upload_id = session['upload_id']
chunk_size = session['chunk_size']  # 20 MB
total_chunks = session['total_chunks']

print(f"Upload session created: {upload_id}")
print(f"Will need {total_chunks} chunks of {chunk_size} bytes each")
```

**Response (200 OK):**

```json
{
    "upload_id": "550e8400-e29b-41d4-a716-446655440000",
    "chunk_size": 20971520,
    "total_chunks": 256,
    "message": "Upload session created"
}
```

**Step 2: Upload Chunks**

**Endpoint:**

```
PUT /api/upload/chunked/{upload_id}/chunk/{chunk_index}
```

**Request:**

```http
PUT /api/upload/chunked/550e8400-e29b-41d4-a716-446655440000/chunk/0 HTTP/1.1
Content-Type: multipart/form-data

file: <binary chunk data - 20 MB>
```

**Parameters:**

- `upload_id` (path): UUID returned from init
- `chunk_index` (path): 0-based chunk number
- Body: Raw binary chunk data

**Python Example:**

```python
import requests
from pathlib import Path

def upload_chunks(upload_id, file_path):
    chunk_size = 20 * 1024 * 1024  # 20 MB

    with open(file_path, 'rb') as f:
        chunk_index = 0

        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break

            # Upload chunk with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.put(
                        f'http://localhost:8000/api/upload/chunked/{upload_id}/chunk/{chunk_index}',
                        files={'file': ('chunk.bin', chunk, 'application/octet-stream')}
                    )
                    response.raise_for_status()
                    print(f"Chunk {chunk_index} uploaded")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"Chunk {chunk_index} failed, retrying...")
                    else:
                        raise

            chunk_index += 1

        print(f"All {chunk_index} chunks uploaded")
```

**JavaScript/TypeScript Example:**

```typescript
async function uploadChunks(
    uploadId: string,
    file: File,
    onProgress?: (progress: number) => void,
): Promise<void> {
    const chunkSize = 20 * 1024 * 1024; // 20 MB
    const totalChunks = Math.ceil(file.size / chunkSize);

    for (let i = 0; i < totalChunks; i++) {
        const start = i * chunkSize;
        const end = Math.min(start + chunkSize, file.size);
        const chunk = file.slice(start, end);

        let retries = 3;
        while (retries > 0) {
            try {
                await fetch(
                    `${process.env.NEXT_PUBLIC_API_URL}/api/upload/chunked/${uploadId}/chunk/${i}`,
                    {
                        method: 'PUT',
                        body: (() => {
                            const formData = new FormData();
                            formData.append('file', chunk, `chunk-${i}.bin`);
                            return formData;
                        })(),
                    },
                );

                const progress = ((i + 1) / totalChunks) * 100;
                onProgress?.(progress);
                break;
            } catch (error) {
                retries--;
                if (retries === 0) throw error;
                await new Promise((resolve) => setTimeout(resolve, 1000));
            }
        }
    }
}
```

**Response (200 OK):**

```json
{
    "chunk": 0,
    "status": "ok"
}
```

**Step 3: Check Upload Status (Optional)**

**Endpoint:**

```
GET /api/upload/chunked/{upload_id}/status
```

**Use When:**

- Resuming interrupted upload
- Checking which chunks failed
- Tracking progress

**Python Example:**

```python
import requests

response = requests.get(
    'http://localhost:8000/api/upload/chunked/550e8400-e29b-41d4-a716-446655440000/status'
)

status = response.json()
print(f"Uploaded: {status['uploaded_chunks']}/{status['total_chunks']}")
print(f"Status: {status['status']}")

if status['status'] in ('uploading', 'processing'):
    print(f"Progress: {status['progress_pct']:.2f}%")
```

**Response (200 OK):**

```json
{
    "upload_id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "large_model.safetensors",
    "total_size": 5368709120,
    "total_chunks": 256,
    "chunk_size": 20971520,
    "uploaded_chunks": [0, 1, 2],
    "status": "uploading",
    "progress_pct": 1.17,
    "processing_pct": null,
    "error": null,
    "result": null
}
```

**Step 4: Complete Upload**

**Endpoint:**

```
POST /api/upload/chunked/{upload_id}/complete
```

**Python Example:**

```python
import requests
import time

# Complete upload
response = requests.post(
    'http://localhost:8000/api/upload/chunked/550e8400-e29b-41d4-a716-446655440000/complete'
)

print("Upload completed, processing started")

# Wait for processing and poll for results
for i in range(120):  # Wait up to 2 minutes
    try:
        report = requests.get(
            'http://localhost:8000/api/report/550e8400-e29b-41d4-a716-446655440000/pdf'
        )
        if report.status_code == 200:
            print("Report ready!")
            break
    except:
        pass

    time.sleep(1)
```

**Response (202 Accepted):**

```json
{
    "status": "processing",
    "upload_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "RIM-OS audit started; poll /status for progress"
}
```

---

## Report APIs

### Get PDF Report

**Endpoint:**

```
GET /api/report/{upload_id}/pdf
```

**Use When:**

- Need downloadable audit report
- Archiving results
- Sharing with stakeholders

**Python Example:**

```python
import requests

response = requests.get(
    'http://localhost:8000/api/report/550e8400-e29b-41d4-a716-446655440000/pdf'
)

if response.status_code == 200:
    with open('audit_report.pdf', 'wb') as f:
        f.write(response.content)
    print("PDF saved")
else:
    print("Report not yet generated, try again in a few seconds")
```

**Response:**

- Status: 200 OK
- Content-Type: application/pdf
- Body: PDF binary file

---

### Get HTML Report

**Endpoint:**

```
GET /api/report/{upload_id}/html
```

**Python Example:**

```python
import requests

response = requests.get(
    'http://localhost:8000/api/report/550e8400-e29b-41d4-a716-446655440000/html'
)

html_content = response.text
```

**Response:**

- Status: 200 OK
- Content-Type: text/html
- Body: Interactive HTML report

---

### Get SVG Visualization

**Endpoint:**

```
GET /api/report/{upload_id}/svg
```

**Returns:**

- Chain-anchored global manifold viewport (not per-artifact isolated seed)
- Artifact position marker rendered within shared chain tiling
- Chain context label (`Global M · Chain={n} blocks`)
- Risk badge and τ preview label

**Python Example:**

```python
import requests

response = requests.get(
    'http://localhost:8000/api/report/550e8400-e29b-41d4-a716-446655440000/svg'
)

svg_content = response.text

# Can embed in HTML
html = f"""
<html>
  <body>
    {svg_content}
  </body>
</html>
"""
```

---

## NFT Minting APIs

### 1. Upload Metadata (IPFS)

**Endpoint:**

```
POST /api/ipfs/upload
```

**Request:**

```json
{
  "uploadId": "550e8400-e29b-41d4-a716-446655440000",
  "fileHash": "3f...64hex",
  "metadata": {
    "name": "RIMOS #550e8400",
    "description": "Audit certificate metadata",
    "attributes": [{ "trait_type": "Risk Level", "value": "Medium Risk" }]
  },
  "auditData": {
    "integrityScore": 91.2,
    "riskLevel": "Medium Risk"
  }
}
```

**Response (200 OK):**

```json
{
  "url": "https://gateway.pinata.cloud/ipfs/Qm...",
  "cid": "Qm...",
  "provider": "pinata",
  "fallbackUsed": false
}
```

### 2. Prepare Mint

**Endpoint:**

```
POST /api/mint/prepare
```

**Request:**

```json
{
  "uploadId": "550e8400-e29b-41d4-a716-446655440000",
  "walletAddress": "So1111111111111111111111111111111111111111111",
  "fileHash": "3f...64hex",
  "metadata": {
    "name": "RIMOS #550e8400",
    "symbol": "RIMOS"
  },
  "metadataUrl": "https://gateway.pinata.cloud/ipfs/Qm...",
  "auditData": {
    "integrityScore": 91.2
  }
}
```

**Response (200 OK):**

```json
{
  "metadata": {
    "url": "https://gateway.pinata.cloud/ipfs/Qm...",
    "provider": "custom",
    "fallbackUsed": false
  },
  "mintHash": "ab...64hex",
  "nftMetadata": {
    "name": "RIMOS #550e8400",
    "symbol": "RIMOS"
  }
}
```

### 3. Finalize Mint

**Endpoint:**

```
POST /api/mint/finalize
```

**Request:**

```json
{
  "mintAddress": "So1111111111111111111111111111111111111111111",
  "uploadId": "550e8400-e29b-41d4-a716-446655440000",
  "signature": "5vFHkqa8tgvhixVV..."
}
```

**Response (200 OK):**

```json
{
  "success": true,
  "message": "Mint successfully finalized"
}
```

### NFT Feature Flag

Mint UI is optional in frontend and controlled by:

```env
NEXT_PUBLIC_ENABLE_NFT=true
```

---

## Error Handling

### Error Response Format

All errors follow this format:

```json
{
    "detail": "Error message",
    "error_code": "ERROR_TYPE",
    "timestamp": "2026-03-18T14:30:00Z",
    "upload_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Common Error Codes

| Code                     | Status | Cause                         | Solution                        |
| ------------------------ | ------ | ----------------------------- | ------------------------------- |
| `FILE_TOO_LARGE`         | 413    | File > 10 GB                  | Split into smaller files        |
| `FILE_NOT_SUPPORTED`     | 400    | Wrong file type               | Use supported format            |
| `INVALID_CHUNK_SIZE`     | 400    | Chunk size > 20 MB            | Split chunks into 20 MB or less |
| `SESSION_EXPIRED`        | 410    | Session inactive > 2 hours    | Restart from init               |
| `SESSION_NOT_FOUND`      | 404    | Wrong upload_id               | Verify upload_id is correct     |
| `CHUNK_ALREADY_RECEIVED` | 409    | Chunk uploaded twice          | Skip and continue               |
| `SIGNATURE_INVALID`      | 422    | Signature verification failed | Check signing key               |
| `DISK_SPACE_LOW`         | 507    | Insufficient disk space       | Free up disk space on server    |
| `PROCESSING_TIMEOUT`     | 504    | Audit took > 1 hour           | Try with smaller file           |
| `REPORT_NOT_READY`       | 202    | Report still generating       | Poll again in 5-10 seconds      |

### Error Handling Best Practices

**Python:**

```python
import requests
from requests.exceptions import RequestException, Timeout

def upload_with_retry(file_path, max_retries=3):
    for attempt in range(max_retries):
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(
                    'http://localhost:8000/api/upload',
                    files={'file': f},
                    timeout=300
                )
            response.raise_for_status()
            return response.json()

        except Timeout:
            print(f"Timeout on attempt {attempt + 1}")
            if attempt == max_retries - 1:
                raise

        except requests.HTTPError as e:
            error = e.response.json()

            if e.response.status_code == 413:
                print("File too large, use chunked upload")
                raise

            if e.response.status_code == 400:
                print(f"Invalid file: {error['detail']}")
                raise

            # Retry on server errors
            if 500 <= e.response.status_code < 600:
                print(f"Server error, retrying...")
                continue

            raise
```

**TypeScript:**

```typescript
async function uploadWithErrorHandling(file: File): Promise<string> {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL}/api/upload`,
            {
                method: 'POST',
                body: formData,
            },
        );

        if (!response.ok) {
            const error = await response.json();

            if (response.status === 413) {
                throw new Error(
                    'File too large. Use chunked upload for files > 100 MB',
                );
            }

            if (response.status === 400) {
                throw new Error(`File error: ${error.detail}`);
            }

            throw new Error(error.detail || 'Upload failed');
        }

        const result = await response.json();
        return result.uploadId;
    } catch (error) {
        console.error('Upload failed:', error);
        throw error;
    }
}
```

---

## Code Examples

### Full Upload Workflow (Python)

```python
import requests
import time

class RIMOSClient:
    def __init__(self, base_url='http://localhost:8000'):
        self.base_url = base_url

    def upload_small_file(self, file_path: str) -> dict:
        """Upload file < 100 MB"""
        with open(file_path, 'rb') as f:
            response = requests.post(
                f'{self.base_url}/api/upload',
                files={'file': f}
            )
        return response.json()

    def upload_large_file(self, file_path: str):
        """Upload file >= 100 MB with progress tracking"""
        import os

        file_size = os.path.getsize(file_path)

        # Initialize
        init_response = requests.post(
            f'{self.base_url}/api/upload/chunked/init',
            json={
                'filename': os.path.basename(file_path),
                'total_size': file_size,
                'total_chunks': (file_size + chunk_size - 1) // chunk_size,
                'chunk_size': chunk_size,
            }
        )
        upload_id = init_response.json()['upload_id']

        # Upload chunks
        chunk_size = 20 * 1024 * 1024
        with open(file_path, 'rb') as f:
            chunk_idx = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                requests.put(
                    f'{self.base_url}/api/upload/chunked/{upload_id}/chunk/{chunk_idx}',
                    files={'file': ('chunk.bin', chunk, 'application/octet-stream')}
                )

                progress = (chunk_idx * chunk_size / file_size) * 100
                print(f"Uploading: {progress:.1f}%")
                chunk_idx += 1

        # Complete
        requests.post(
            f'{self.base_url}/api/upload/chunked/{upload_id}/complete'
        )

        # Poll for results
        for i in range(120):
            try:
                pdf_response = requests.get(
                    f'{self.base_url}/api/report/{upload_id}/pdf'
                )
                if pdf_response.status_code == 200:
                    return {'upload_id': upload_id, 'status': 'complete'}
            except:
                pass
            time.sleep(1)

        return {'upload_id': upload_id, 'status': 'processing'}

    def get_report(self, upload_id: str, format='pdf'):
        """Get audit report in specified format"""
        response = requests.get(
            f'{self.base_url}/api/report/{upload_id}/{format}'
        )
        return response.content if format == 'pdf' else response.text

# Usage
client = RIMOSClient()

# For small file
result = client.upload_small_file('model.safetensors')
print(f"Score: {result['kpis'][0]['value']}")

# For large file
result = client.upload_large_file('large_model.safetensors')
pdf = client.get_report(result['upload_id'], 'pdf')
```

### Full Upload Workflow (TypeScript/React)

```typescript
import { useState } from 'react';

export function FileUploadComponent() {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<any>(null);

  const CHUNK_SIZE = 20 * 1024 * 1024; // 20 MB
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  async function uploadFile(file: File) {
    setUploading(true);

    try {
      if (file.size < 100 * 1024 * 1024) {
        // Single upload
        await singleUpload(file);
      } else {
        // Chunked upload
        await chunkedUpload(file);
      }
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  }

  async function singleUpload(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_URL}/api/upload`, {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();
    setResult(data);
  }

  async function chunkedUpload(file: File) {
    // Initialize
    const initResponse = await fetch(`${API_URL}/api/upload/chunked/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: file.name,
        total_size: file.size,
        total_chunks: Math.ceil(file.size / CHUNK_SIZE),
        chunk_size: CHUNK_SIZE,
      }),
    });

    const { upload_id } = await initResponse.json();

    // Upload chunks
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);

      await fetch(
        `${API_URL}/api/upload/chunked/${upload_id}/chunk/${i}`,
        {
          method: 'PUT',
          body: (() => {
            const formData = new FormData();
            formData.append('file', chunk, `chunk-${i}.bin`);
            return formData;
          })(),
        }
      );

      setProgress(((i + 1) / totalChunks) * 100);
    }

    // Complete
    await fetch(`${API_URL}/api/upload/chunked/${upload_id}/complete`, {
      method: 'POST',
    });

    // Poll for results
    await pollForResults(upload_id);
  }

  async function pollForResults(uploadId: string) {
    for (let i = 0; i < 120; i++) {
      try {
        const response = await fetch(`${API_URL}/api/report/${uploadId}/pdf`);
        if (response.ok) {
          const dataResponse = await (
            await fetch(`${API_URL}/api/report/${uploadId}/extended`)
          ).json();
          setResult(dataResponse);
          return;
        }
      } catch {
        // Still processing
      }

      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }

  return (
    <div>
      <input
        type="file"
        onChange={e => e.target.files && uploadFile(e.target.files[0])}
        disabled={uploading}
      />

      {uploading && <p>Progress: {progress.toFixed(0)}%</p>}

      {result && (
        <div>
          <p>Score: {result.kpis[0].value}</p>
          <p>Risk: {result.artifactBlock.manifold_hash}</p>
        </div>
      )}
    </div>
  );
}
```

---

## Webhooks & Polling

### Polling Pattern (Current)

```python
import time
import requests

def wait_for_report(upload_id, max_wait=600):
    """Poll until report is ready (max 10 minutes)"""

    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(
                f'http://localhost:8000/api/report/{upload_id}/pdf'
            )
            if response.status_code == 200:
                return response.content
        except:
            pass

        time.sleep(2)  # Poll every 2 seconds

    raise TimeoutError(f"Report not ready after {max_wait} seconds")
```

### Webhook Support (Future)

Future versions may support webhooks:

```
POST {{webhook_url}} with payload:
{
  "event": "upload.completed",
  "upload_id": "...",
  "status": "success",
  "result": {...}
}
```

---

**Last Updated:** March 23, 2026
**Version:** 1.1
