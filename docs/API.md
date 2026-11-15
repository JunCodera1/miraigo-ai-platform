# API reference (v1)

Base URL: `http://<host>:8090`. Machine-readable contract: [`openapi.json`](openapi.json) (also served
live at `/openapi.json`, browsable at `/docs`). All `/api/v1/*` routes need authentication
([AUTH.md](AUTH.md)); `/health/*` does not.

## Envelope

Same shape as the MiraiGo backend's `ApiResponse`, plus `requestId`. Null envelope fields are omitted.

```json
{ "status": 200, "message": "Success", "data": { }, "path": "/api/v1/...", "timestamp": "2026-11-14T05:45:57.713Z", "requestId": "af22ef67..." }
{ "status": 413, "message": "The recording is longer than the 30 second limit for this endpoint.", "errorCode": "AI_AUDIO_TOO_LONG", "path": "...", "timestamp": "...", "requestId": "..." }
```

Send `X-Request-Id` (8–64 chars of `[A-Za-z0-9._-]`) to correlate with your own logs; otherwise one is
generated. It is returned in the `X-Request-Id` header and the body.

## `POST /api/v1/speech/transcribe`

`multipart/form-data`

| Field | Type | Default | Notes |
|---|---|---|---|
| `file` | file | required | wav, mp3, m4a/aac, ogg/opus, webm, flac, amr, 3gp, mp4/mov/mkv (audio track used). ≤ 25 MB, ≤ 120 s |
| `model` | string | routing | a registry id from `/api/v1/models`; no fallback when set |
| `wordTimestamps` | bool | false | per-token times (characters/kana for Japanese models) |
| `responseFormat` | `json`\|`srt`\|`vtt` | `json` | subtitle formats return plain text with `X-Model` header |

```json
{ "text": "うちの中学は弁当制で…", "language": "ja", "durationSeconds": 7.2,
  "segments": [ { "start": 0.0, "end": 7.2, "text": "…", "words": [ { "text": "う", "start": 0.48, "end": 0.6 } ] } ],
  "meta": { "model": "sensevoice-small-int8", "provider": "sherpa_onnx", "processingMs": 163, "estimatedCostUsd": 0.0, "fallbackUsed": false } }
```

Recordings longer than 20 s are cut at pauses (VAD) before recognition, so long files yield several segments.

## `POST /api/v1/pronunciation/evaluate`

`multipart/form-data`: `file` (≤ 30 s), `referenceText` (1–200 chars, the sentence the learner read), optional `model`.
Uses its own model route (`routing.pronunciation`, default ReazonSpeech → SenseVoice → Parakeet): a
recogniser that adds punctuation and "repairs" speech is better for transcripts than for assessment.

```json
{ "method": "asr_alignment_v0",
  "referenceText": "東京に行きました", "recognizedText": "ときょうに行きました",
  "scores": { "overall": 90, "accuracy": 90, "completeness": 100 },
  "counts": { "morae": 10, "matched": 9, "substituted": 0, "omitted": 1, "inserted": 0 },
  "speechRateMoraePerSecond": 5.2, "durationSeconds": 2.1,
  "words": [
    { "text": "東京", "expected": "とーきょー", "heard": "ときょー", "status": "partial",
      "issues": [ { "type": "long_vowel_shortened", "expected": "ー", "heard": null,
                    "message": "A long vowel was cut short. Hold it for one more beat." } ] },
    { "text": "に", "expected": "に", "heard": "に", "status": "ok", "issues": [] } ],
  "limitations": [ "…" ],
  "meta": { "model": "reazonspeech-zipformer-ja", "…": "…" } }
```

- `accuracy` = matched / reference morae; `completeness` = reference morae not omitted; `overall` =
  1 − (substitutions + omissions + insertions) / reference morae. Extra speech lowers `overall` only.
- Long vowels are written `ー` in `expected`/`heard` so とうきょう and とーきょー compare equal.
- Issue types: `long_vowel_shortened`, `vowel_lengthened`, `sokuon_missing`, `sokuon_added`,
  `n_missing`, `n_added`, `voicing`, `youon`, `vowel`, `consonant`, `mismatch`, `omitted`, `extra_sound`.
- Calibration (lab E-002): correct native read speech scores median 96–99; 86–90 % of native
  utterances score ≥ 90. Treat ≥ 90 as "good" and don't present 80–89 as failure.
- Silent recording → 422 `AI_AUDIO_EMPTY`; reference without Japanese → 422 `AI_TEXT_NOT_JAPANESE`.

## `POST /api/v1/language/analyze`

JSON `{ "text": "…", "splitMode": "A" | "B" | "C" }` (≤ 2000 chars; C = longest units, default).

```json
{ "text": "私は猫が好きです。", "reading": "わたしはねこがすきです。", "romaji": "watashi wa neko ga suki desu",
  "tokens": [ { "surface": "私", "lemma": "私", "reading": "わたし", "romaji": "watashi", "pos": "pronoun",
                "posDetail": ["代名詞"], "conjugationType": null, "conjugationForm": null, "conjugationFormEn": null,
                "furigana": [ { "text": "私", "reading": "わたし" } ], "start": 0, "end": 1, "isWord": true, "isOov": false } ] }
```

`reading` keeps particles as written (は, へ, を); `romaji` uses their spoken form (wa, e, o).
`furigana` is set only on tokens containing kanji, split so kana already in the word get no ruby
(食べる → 食[た]べる).

## `GET /api/v1/models`

Every registry entry with `available`, `unavailableReason`, `license`, `source`, `routingRole` (role in
transcription) and `routingRoles` (per route: `asr`, `pronunciation` → `primary` | `fallback` | `none`).

## `GET /health/live`, `GET /health/ready`

`ready` reports per-capability availability (`asr`, `pronunciation`, `language`) and `status`
`ok`/`degraded`. Use `live` for container liveness and `ready` for load-balancer routing.

## `GET /api/v1/admin/usage`

Per-model requests, failures, audio seconds, processing time and estimated cost since start.
ADMIN role or service key only.
