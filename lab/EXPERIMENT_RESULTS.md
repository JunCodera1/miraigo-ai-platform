# Experiment Results

Own measurements only. Each entry: setup, numbers, how to reproduce, what it does NOT show.
Raw per-utterance reports: `~/.local/share/japanese-ai-platform/eval/reports/*.json` (outside git).

## E-001 Japanese ASR on CPU — FLEURS ja test (2026-11-14) [V]
Setup: first 100 utterances of `google/fleurs` ja_jp test (CC-BY-4.0), 21.7 min native read speech,
90 unique sentences (FLEURS repeats sentences across speakers).
Ryzen 5 7535HS, CPU only, 4 threads, int8 where available, one model per process under
`run-capped.sh` (memory cap, no swap). CER = corpus-level edit distance after NFKC and removing
Unicode Z/P/S characters (kanji/kana choice counts). Kana CER = same on Sudachi readings (script-agnostic).
Model RAM = RSS increase when loading. Script: `scripts/eval_asr.py`.

| Model | CER | Kana CER | RTF | p50 / p90 per utt. | Model RAM | Load |
|---|---|---|---|---|---|---|
| SenseVoice Small int8 (2024-07-17) | **0.085** | 0.053 | 0.023 | 0.28 / 0.40 s | 372 MB | 1.0 s |
| Parakeet TDT-CTC 0.6B ja int8 | **0.085** | 0.056 | 0.047 | 0.59 / 0.84 s | 972 MB | 2.2 s |
| ReazonSpeech k2 v2 Zipformer int8 | 0.100 | 0.053 | 0.019 | 0.23 / 0.33 s | 278 MB | 1.3 s |
| Moonshine base ja (quantized) | 0.122 | 0.100 | 0.036 | 0.46 / 0.65 s | 346 MB | 0.8 s |
| Whisper small (faster-whisper int8, beam 5) | 0.135 | 0.064 | 0.155 | 1.97 / 2.33 s | 737 MB | 52 s (incl. download) |
| Legacy prototype `miraigo-ai-server` (LID + Whisper base) | 0.346 | 0.241 | 0.337 | 4.50 / 4.94 s | n/a (container) | — |

Notes:
- Legacy: 13/100 empty transcripts (all 7–11 s clips; cause not investigated — [H] its RMS gate,
  language-ID misfire or hallucination filter), plus misrecognitions; its README claim
  "Whisper Small" is wrong — it loads Base.
- Kana CER gap (CER 0.085→0.053) = differences in kanji/kana choice and number formatting, which do
  not matter for pronunciation scoring.
- Pitfall: sherpa-onnx archive `sense-voice-…-int8-2025-09-09` is a Cantonese fine-tune; on these
  clips it gave CER 0.79 (3-utterance check). Not a SenseVoice quality problem.
Not shown: learner/non-native speech, noisy/conversational audio, long-form media, GPU, concurrency.
Sample is 100 utterances, so differences under ~1 point are not meaningful (SenseVoice vs Parakeet = tie).
Peak RSS printed by the script (~2.3 GB) is dominated by the eval harness (decoded dataset, Arrow), not the model.

## E-002 Pronunciation scoring strictness on correct native speech (2026-11-14) [V]
Setup: E-001 hypotheses re-scored with `asr_alignment_v0` against the FLEURS reference text
(a perfect reader should get ~100). Long sentences (avg ~13 s) with foreign names.

| ASR used | median overall | mean | p10 | utterances ≥ 90 |
|---|---|---|---|---|
| SenseVoice | 96.5 | 94.9 | 88 | 86 / 100 |
| ReazonSpeech | 99.0 | 95.3 | 90 | 90 / 100 |
| Parakeet | 99.0 | 95.0 | 89 | 89 / 100 |
| Whisper small | 95.0 | 93.7 | 86 | 80 / 100 |

Reading: ~10–14 % of correct native utterances fall below 90 because of recogniser errors (mostly
proper nouns, foreign words, numbers). Practice sentences are shorter and simpler, so this is a
pessimistic bound. → UI threshold "≥ 90 = good"; never present 80–89 as failure.
Not shown: whether real learner errors are detected (sensitivity). Needs learner recordings.

## E-003 Live system checks (2026-11-14) [V]
Server on :8090 (auth=backend) and :8091 (auth=none), real models, real MiraiGo backend on :8080.
- Auth: no token → 401 `AI_AUTH_REQUIRED`; garbage token → backend 401 → `AI_AUTH_INVALID`. Valid
  token NOT exercised live (session had no credentials); covered by mocked-backend tests.
- Transcribe: wav, WebM/Opus (browser format) and MP4 video all decoded; ja.wav 7.2 s → 163 ms.
  SRT/VTT output correct. Fallback model selectable by `model`.
- Pronunciation: FLEURS clip + its own reference → 100/100/100; same clip + unrelated sentence → overall 0.
- Input safety: an M3U playlist renamed `.mp3` → 400 `AI_AUDIO_INVALID`; 40 s clip to pronunciation → 413.
- WebSocket: two clips streamed at **1× real time** (100 ms frames) → 4 segments, `done`; each
  segment arrived 0.32–0.60 s after the speech ended (includes the 0.35 s pause that closes an
  utterance). Short pauses split sentences.
- Dart client (`examples/flutter`): `dart analyze` clean; smoke run OK; bad token → `AiException(401 AI_AUTH_INVALID)`.
- Expo client (`examples/expo/ai-client.ts`): typechecks inside the app (`npx tsc --noEmit` exit 0)
  and was executed under Node 26 against the server: analyze, transcribe (WebM `Blob`), pronunciation,
  typed 422 error, and on a bad token 401 `AI_AUTH_INVALID` after exactly one refresh attempt.
  (Constructor parameter properties were removed so Node type-stripping can run it.)
- Docker: `cp .env.example .env && docker compose up -d --build` → healthy, read-only root, models
  mounted `:ro`, 552 MiB; garbage token → 401 (container reaches backend via host.docker.internal).
- Pronunciation route (D-016) serves from ReazonSpeech; FLEURS clip + own reference → 100/100/100.
