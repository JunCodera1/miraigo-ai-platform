# AI Architecture

```
 Expo app / web / Flutter ──HTTPS──► japanese-ai-platform :8090 ──GET /api/v1/users/me──► miraigo-be :8080
        │  Bearer <backend access token>        │                                              (token check, D-009)
        │                                       ├─ gateway      FastAPI routes, envelope, request id, CORS,
        │                                       │               auth dependency, rate limit, error mapping
        │                                       ├─ pipelines    pronunciation: audio → ASR → morae → align → feedback
        │                                       ├─ orchestration CapabilityRouter: registry chain, availability skip,
        │                                       │               retries (transient only), timeout, concurrency slots,
        │                                       │               cost estimate, usage ledger
        │                                       ├─ model_registry models.yaml (validated)
        │                                       ├─ providers    ASRProvider adapters: sherpa-onnx | faster-whisper |
        │                                       │               OpenAI-compatible HTTP | legacy prototype HTTP
        │                                       └─ services     audio intake (ffprobe/ffmpeg), VAD, subtitles,
        │                                                       Sudachi analyzer, kana rules, mora scoring
        └── backend stays the system of record (users, courses, vocab SRS, JLPT); the AI platform stores nothing.
```

## Principles (as implemented)
1. **Algorithm before model, local model before API.** Readings, furigana, romaji, conjugation and
   mora scoring are deterministic code. ASR is local; a paid API is a fallback.
2. **Providers are replaceable.** Business code sees `ASRProvider`/`Transcription`; models are YAML
   entries; a caller-chosen model is never silently swapped.
3. **Fail closed, explain clearly.** Every error has a stable `errorCode`; auth failures never let
   requests through; every result says which model produced it and whether a fallback was used.
4. **User data is transient.** Uploads → private temp file → deleted after decoding. Logs carry ids,
   sizes, timings, model ids — never audio, text or tokens.
5. **Bounded resources.** Upload size, duration per endpoint, concurrency slots with queue timeout,
   per-user rate limits, container memory limit, VAD-cut long audio.

## Request flows
- `POST /speech/transcribe`: auth → inference quota → stage upload (size cap) → ffprobe allow-list →
  ffmpeg decode to 16 kHz f32 (duration cap) → router (slot, timeout, fallback) → JSON or SRT/VTT.
- `POST /pronunciation/evaluate`: same intake (30 s cap) → reference → Sudachi readings → morae
  (mid-mora splits glued, long vowels canonical per word, particles as spoken) → silence check →
  ASR → align (phonetic substitution cost) → per-word status + typed issues → scores.
- `WS /speech/stream`: origin check → first message auth → PCM16 frames → Silero VAD → each closed
  utterance through the router → `segment` events.

## Extension points (next capabilities)
- LLM capability: add `capability: llm` to the registry, an `LLMProvider` contract
  (`generate(messages, schema)`), Anthropic adapter (default `claude-opus-5-5`, model id in config,
  refusal + fallback handling) and an OpenAI-compatible adapter; grammar correction pipeline =
  Sudachi analysis + LLM structured output + deterministic diff.
- Long media: job queue (Redis + worker) with `POST /multimedia/jobs` → poll/SSE; VAD chunking
  already exists.
- Personalisation: needs events from the backend (pronunciation issues per user) — decide whether
  the backend stores them (preferred) or the platform gets a database.
