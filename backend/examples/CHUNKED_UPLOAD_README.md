# Chunked Upload for Large Files

Optimized for 3–10 GB audit artifacts (.lm3z, .rim0, .rim95). Target: **<10 minutes** for a 3–5 GB file (vs ~30 min single-request upload).

## Features

- **Chunked upload** – Split file into 10 MB chunks
- **Parallel uploads** – 8 concurrent requests by default
- **Low memory** – Server writes chunks directly to disk at offset
- **Resumable** – Save upload ID; retry missing chunks if connection drops
- **Streaming merge** – No full-file load; RIM audit streams from disk

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload/chunked/init` | Start session, get `upload_id` |
| PUT | `/api/upload/chunked/{id}/chunk/{index}` | Upload single chunk |
| GET | `/api/upload/chunked/{id}/status` | Get progress (for resume) |
| POST | `/api/upload/chunked/{id}/complete` | Merge + run RIM audit |

## Flow

1. **Init** – `POST /init` with `filename`, `total_size`, `total_chunks`, `chunk_size`
2. **Upload** – `PUT /chunk/{index}` for each chunk (parallelize)
3. **Complete** – `POST /complete` when all chunks received
4. **Resume** – If interrupted: `GET /status`, then upload only missing chunks

## Config (`.env` / `Settings`)

```
chunk_upload_enabled=true
chunk_size_bytes=10485760        # 10 MB
chunk_upload_max_concurrent=8
chunk_upload_session_ttl_seconds=3600
```

## Frontend Example

Open `chunked_upload_frontend.html` in a browser. Configure API URL, concurrency, and chunk size. Select a file and upload. If the connection drops, paste the upload ID into "Resume Upload ID" and re-select the same file to continue.

## Expected Performance

- Single request: ~2.6 MB/s → 3.8 GB ≈ 25 min
- 8 parallel chunks: ~8× throughput (limited by network) → ~4–6 min upload + ~2–4 min RIM audit ≈ **<10 min total**
