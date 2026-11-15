# Deployment

## Shape
One stateless container (FastAPI + Uvicorn, single process). Models on a mounted volume. No database:
nothing about users is stored; uploads live in a private temp file only while being decoded.

## Sizing (measured on Ryzen 5 7535HS, CPU only)
| Item | Value |
|---|---|
| Container memory, both route primaries loaded | 552 MiB measured (`docker stats`, compose run); 360–420 MiB with one model |
| Each additional loaded fallback | +280 MB (ReazonSpeech) / +970 MB (Parakeet) |
| Decode speed | ~1.4 s per audio minute on 4 threads (RTF 0.023) |
| Pronunciation request (3–10 s clip) | ~0.1–0.3 s model time + ffmpeg |

`JAI_MAX_CONCURRENT_INFERENCE` (default 1) bounds simultaneous local decodes; excess requests queue
up to `JAI_INFERENCE_QUEUE_TIMEOUT_SECONDS` then get 503 `AI_BUSY`. Raise it to the number of
physical cores ÷ 4 threads. Estimate (not measured): a 2 vCPU / 4 GB VM handles 1 decode at a time; for more,
scale out replicas (and move rate limiting to Redis — the in-process limiter is per replica).

Not measured: throughput under concurrent load, GPU (the RTX 2050 here was not used), the EC2 host.

## Steps
```bash
cp .env.example .env    # set JAI_ENV=production, JAI_BACKEND_BASE_URL, JAI_CORS_ALLOWED_ORIGINS, JAI_DOCS_ENABLED=false
scripts/download_models.sh ./models
docker compose up -d --build
curl -f http://localhost:8090/health/ready
```
Put it behind the same TLS reverse proxy as the backend (e.g. `https://api.example.com/ai/` →
`:8090`, forwarding `Upgrade` for WebSocket). The image runs as a non-root user with a read-only
root filesystem; uploads go to a 256 MB tmpfs on `/tmp` (must be mode 1777 — a root-owned tmpfs breaks uploads for the non-root user).

## Checklist before production
- `JAI_ENV=production` (refuses `JAI_AUTH_MODE=none`), docs off, explicit CORS origins.
- Network: only the proxy reaches `:8090`; the platform must reach the backend's `/api/v1/users/me`.
- Logs are JSON to stdout and contain request ids, paths, status, timings, model ids — never audio,
  transcripts, learner text or tokens.
- If a remote provider (e.g. OpenAI) is enabled, audio leaves your infrastructure: say so in the privacy policy.
- Licence: SenseVoice requires attribution and keeping the model name (FunASR licence v1.1); Parakeet
  is CC-BY-4.0 (attribution). Moonshine Japanese is non-commercial and is disabled.
