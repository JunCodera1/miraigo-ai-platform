# MiraiGo Japanese AI Platform

A standalone service that gives MiraiGo clients (the Expo app, a web app, a Flutter app) Japanese speech
and language intelligence through one versioned API. It runs separately from the MiraiGo backend and
the app, and accepts the same access token as the backend.

| Capability | Endpoint | How it works | Status |
|---|---|---|---|
| Japanese speech-to-text, timestamps, SRT/WebVTT subtitles | `POST /api/v1/speech/transcribe` | Local ASR model chosen by the model registry, with fallbacks | working, measured |
| Live transcription | `WS /api/v1/speech/stream` | Voice activity detection cuts utterances, each one is transcribed | working |
| Pronunciation feedback (mora level) | `POST /api/v1/pronunciation/evaluate` | Reference text and recognised speech → morae → alignment → typed issues | working, v0 method (see limits) |
| Morphological analysis, readings, furigana, romaji, conjugation | `POST /api/v1/language/analyze` | Sudachi dictionary + kana rules, no LLM | working |
| Model catalogue and availability | `GET /api/v1/models` | Model registry | working |

Not built yet: LLM features (grammar correction, explanations, tutor), pitch-accent scoring, TTS,
long-video jobs. The plan and the evidence behind every choice are in [`lab/`](lab/README.md)
(start with `lab/CURRENT_STATE.md`).

## Measured quality (this machine, CPU only)

FLEURS Japanese test set, first 100 utterances (21.7 min of read speech). Corpus CER after NFKC and
removing punctuation. Full method and per-utterance output: `lab/EXPERIMENT_RESULTS.md` (E-001).

| Model (registry id) | CER | Kana CER | Speed (RTF) | Model RAM | Role |
|---|---|---|---|---|---|
| `sensevoice-small-int8` | **8.5 %** | 5.3 % | 0.023 | ~370 MB | transcription primary |
| `parakeet-tdt-ctc-0.6b-ja` | 8.5 % | 5.6 % | 0.047 | ~970 MB | fallback |
| `reazonspeech-zipformer-ja` | 10.0 % | 5.3 % | 0.019 | ~280 MB | pronunciation primary, transcription fallback (Apache-2.0) |
| `whisper-small-ct2` | 13.5 % | 6.4 % | 0.155 | ~740 MB | available, not routed |
| `moonshine-base-ja` | 12.2 % | 10.0 % | 0.036 | ~350 MB | disabled: non-commercial licence |
| legacy prototype (port 8000) | 34.6 % | 24.1 % | 0.337 | — | baseline; 13/100 empty outputs |

RTF 0.023 means one minute of audio takes about 1.4 s on 4 CPU threads (Ryzen 5 7535HS). 100 utterances
(90 unique sentences) of native read speech; learner speech has not been measured. Pronunciation uses
its own route (ReazonSpeech first): on correct native speech it scored ≥ 90 on 90/100 utterances (E-002).

## Quick start (local)

Requires Python ≥ 3.12 and ffmpeg.

```bash
python -m venv ~/.local/share/japanese-ai-platform/venv
~/.local/share/japanese-ai-platform/venv/bin/pip install -e ".[local,dev]"
scripts/download_models.sh            # ~1 GB into ~/.local/share/japanese-ai-platform/models
cp .env.example .env                  # then edit
~/.local/share/japanese-ai-platform/venv/bin/japanese-ai
```

The API listens on `http://127.0.0.1:8090`; interactive docs at `/docs`, OpenAPI at `/openapi.json`.
Keep the virtualenv and models outside the repository (git-ignored either way; they are large).

For local development without the backend, set `JAI_AUTH_MODE=none` (refused when `JAI_ENV=production`).

## Docker

```bash
scripts/download_models.sh ./models
docker compose up -d --build
curl http://localhost:8090/health/ready
```

Models are mounted, not baked into the image. The compose file sets a 3 GB memory limit, a read-only
root filesystem and a tmpfs for uploads. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Calling the API

```bash
TOKEN=...   # the learner's MiraiGo access token
curl -H "Authorization: Bearer $TOKEN" -F file=@clip.m4a -F referenceText=東京に行きました \
     http://localhost:8090/api/v1/pronunciation/evaluate
```

Every JSON response uses the backend's envelope (`status`, `message`, `errorCode?`, `data?`,
`errors?`, `path`, `timestamp`) plus `requestId`. Details:

- [`docs/API.md`](docs/API.md) — endpoints, request/response examples
- [`docs/AUTH.md`](docs/AUTH.md) — how tokens are checked
- [`docs/ERRORS.md`](docs/ERRORS.md) — error codes
- [`docs/STREAMING.md`](docs/STREAMING.md) — WebSocket protocol
- [`docs/INTEGRATION.md`](docs/INTEGRATION.md) — Expo and Flutter clients ([`examples/expo`](examples/expo/ai-client.ts), [`examples/flutter`](examples/flutter))
- [`docs/MODELS.md`](docs/MODELS.md) — adding or swapping models, running the evaluation

## Layout

```
src/japanese_ai/
  core/            settings, errors, envelope, structured logging
  gateway/         FastAPI app, middleware, routes, request dependencies
  orchestration/   capability router (fallback, retries, timeouts, concurrency, cost), usage ledger
  model_registry/  models.yaml + loader/validator
  providers/       provider contracts + adapters (sherpa-onnx, faster-whisper, OpenAI-compatible, legacy)
  services/        speech (audio intake, VAD, subtitles), language (analyzer, kana), pronunciation (scoring)
  pipelines/       multi-step flows (pronunciation evaluation)
  infrastructure/  authentication, rate limiting
tests/             104 tests; real-model tests run only when models are on disk
scripts/           eval_asr.py (reusable model evaluation), run-capped.sh, download_models.sh
examples/          Expo (TypeScript) and Flutter (Dart) clients
```

## Tests

```bash
~/.local/share/japanese-ai-platform/venv/bin/python -m pytest          # all
~/.local/share/japanese-ai-platform/venv/bin/python -m pytest -m models  # real-model tests only
~/.local/share/japanese-ai-platform/venv/bin/ruff check src tests scripts
```

## Status

Prototype foundation, not production-validated. Before production: load test on the target server,
measure learner (non-native) speech, owner review of the SenseVoice licence for transcription (custom
FunASR licence: attribution and keeping the model name required; `JAI_ASR_MODEL=reazonspeech-zipformer-ja`
switches to Apache-2.0 only), shared rate limiting for more than one replica,
and a decision on retention of uploaded audio (currently: never stored — files are deleted right
after decoding).
