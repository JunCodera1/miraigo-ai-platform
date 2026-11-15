# Provider Comparison (2026-11-12)

Commercial vs open options per capability. Prices are list prices in USD.
Labels: [V] read on the vendor's own page this session, [S] secondary source only, [H] recall — verify before budgeting,
[E] own experiment (see `EXPERIMENT_RESULTS.md`).
Evidence for open ASR models: `research/speech-ai/asr-candidates.md`.

## 1. Speech-to-text

| Provider / model | Price | Japanese | Streaming | Notes |
|---|---|---|---|---|
| **Local: sherpa-onnx / faster-whisper** | $0 + compute | yes | VAD-segmented | no data leaves the server; accuracy measured in [E] |
| OpenAI `gpt-transcribe` | $0.0045/min [V] | yes | via realtime models | 6.07 % strict CER on asr-ja-bench per Haas authors [S] |
| OpenAI `gpt-4o-transcribe` / `gpt-4o-mini-transcribe` | $0.006 / $0.003 per min [V] | yes | — | |
| OpenAI Whisper | $0.006/min [V] | yes | no | |
| OpenAI `gpt-realtime-whisper`, `gpt-live-transcribe` | $0.017/min [V] | yes | yes | live transcription |
| Google `gemini-3.5-transcribe` | $0.003/min audio in + $0.002/min text out [V] | yes [H] | `-live` variant $0.005 + $0.004 | free tier exists; **free-tier data is used to improve Google products**, paid is not [V] |
| Deepgram Nova-3 | $0.0043/min batch, $0.0077/min streaming (multilingual $0.0052 / $0.0092) [V] | page says "60+ languages", Japanese not named [V] | yes | billed per second |
| Groq `whisper-large-v3-turbo` | ≈$0.04/hour, 10 s minimum per request [S] | yes | no | pricing page showed no table when fetched |
| ElevenLabs Scribe v2 | ≈$0.22–0.40/hour [S] | yes [H] | realtime variant | |
| Azure Speech | not readable when fetched; ≈$1/hour real-time [H] | yes | yes | only vendor with built-in pronunciation assessment; 5 h/month free [V] |

Sources fetched 2026-11-12: developers.openai.com/api/docs/pricing · aistudio.google.com/docs/pricing ·
deepgram.com/pricing · azure.microsoft.com/…/speech-services. Groq and ElevenLabs figures are from
third-party comparison pages only.

**Cost scale.** 1,000 learners × 10 min of speaking practice per day = 300,000 min/month:
`gpt-transcribe` ≈ $1,350, `gpt-4o-mini-transcribe` ≈ $900, Deepgram batch ≈ $1,290, Groq turbo ≈ $200 [S],
local = one CPU server. Practice clips are 3–15 s, so a 10 s minimum (Groq) roughly doubles real cost there.

**Recommendation.** Local model first (cost, privacy, and control over the decoder, which pronunciation
scoring needs). Keep one OpenAI-compatible remote adapter as a fallback and for long-form media, where
robustness on noisy audio matters more.

## 2. Pronunciation assessment

| Option | Japanese support | Verdict |
|---|---|---|
| Azure Speech pronunciation assessment | `ja-JP` supported; **no prosody**, no syllable level (en-US only) [V] | word-level second opinion only |
| Self-built (ASR alignment → phoneme-CTC GOP → F0 accent) | full control, mora level | primary path; see `research/pronunciation/assessment-approaches.md` |

## 3. LLM (grammar correction, explanations, tutor)

Per 1M tokens, standard tier.

| Model | Input | Output | Cached input | Source |
|---|---|---|---|---|
| Claude Opus 5.5 `claude-opus-5-5` | $4.00 | $20.00 | $0.20 | [V] Anthropic reference, cached 2026-11-03 |
| Claude Sonnet 5.5 `claude-sonnet-5-5` | $2.00 | $10.00 | $0.10 | [V] same |
| Claude Haiku 5.5 `claude-haiku-5-5` | $0.10 | $0.50 | — | [V] same; prompts ≤100K ($0.50/$2.50 beyond) |
| OpenAI `gpt-6.1-sol` | $2.00 | $10.00 | $0.10 | [V] |
| OpenAI `gpt-6.1-terra` | $1.00 | $5.00 | $0.05 | [V] |
| OpenAI `gpt-6-luna` | $0.10 | $0.50 | $0.01 | [V] |
| Google `gemini-3.8-flash` | $0.75 → $1.50 from 2027-01-01 | $3.75 → $7.50 | $0.075 → $0.15 | [V] |
| Google `gemini-3.5-flash-lite` | $0.30 | $2.50 | $0.03 | [V] |
| Google `gemini-4-carbon` | $2.00 → $4.00 from 2026-12-01 | $10 → $20 | $0.10 → $0.20 | [V] |
| Open weights via llama.cpp / vLLM (Qwen, Gemma) | compute only | | | not evaluated this session |

Not verified this session: Japanese-specific quality ranking between these models. No benchmark was run
(no API keys available), so model choice here rests on price and features only.

**Recommendation [P].** Default to Claude (`claude-opus-5-5`) for tutor and correction quality, with the
model id a config value. The high-volume, simple calls (short vocabulary explanations) are the place to try
a cheaper tier once there is an eval to check quality against — that is a product decision for the owner,
not a default. Keep an OpenAI-compatible adapter so OpenAI, Gemini's compatible endpoint, or a self-hosted
llama.cpp/vLLM server can be swapped in. Use an LLM only where rules cannot do the job: tokenisation,
furigana, romaji, conjugation and SRS scheduling stay algorithmic.

**Cost scale.** A correction call ≈ 600 input + 400 output tokens. Per 100,000 calls:
Opus 5.5 ≈ $1,040, Sonnet 5.5 ≈ $520, Haiku 5.5 ≈ $26, gpt-6.1-terra ≈ $260, gemini-3.5-flash-lite ≈ $118.
Prompt caching of a fixed system prompt cuts the input part by up to ~90 % on cache hits.

## 4. Text-to-speech (not built yet)

| Option | Licence / price | Notes |
|---|---|---|
| Kokoro-82M | Apache-2.0 [V: HF API] | runs in sherpa-onnx (already a dependency); Japanese quality unmeasured |
| VOICEVOX engine | repo licence reported as non-standard by GitHub; per-voice terms, credit required [S] | high-quality Japanese; check each voice's terms |
| AivisSpeech Engine | LGPL-3.0 [V: GitHub API] | Style-Bert-VITS2 based; voice-model licences vary |
| Style-Bert-VITS2 | AGPL-3.0 [V: GitHub API] | AGPL obligations for a network service |
| OpenAI `gpt-4o-mini-tts` | $0.60/1M text in + $12/1M audio out [V] | |
| OpenAI `tts-1` / `tts-1-hd` | $15 / $30 per 1M chars [V] | |
| Google `gemini-3.8-flash-tts` | $0.50 text in + $9 audio out per 1M (doubling 2027-01-01) [V] | |
| Deepgram Aura-2 | $0.030 per 1k chars [V] | Japanese support unverified |
| Azure neural TTS | price not readable; 0.5M chars/month free [V] | |

Grammar examples in the backend already carry an `audioUrl` field, so pre-generating audio offline (batch,
cached by text hash) is cheaper than synthesising per request.

## 5. Decision rule used throughout
1. If an algorithm or dictionary solves it, use that (deterministic, free, testable).
2. Otherwise prefer a local specialised model when it fits the server and its accuracy is measured.
3. Use a commercial API where quality clearly matters more than cost, or as fallback — behind an adapter,
   with the key server-side only.
