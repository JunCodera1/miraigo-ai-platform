# AI Technology Atlas

One line per domain: what to use, why, and the evidence label. Details live in the linked files.
[V] verified this project, [E] own experiment, [B] third-party benchmark, [H] unverified, [P] proposal.

## Speech
| Need | Choice | Alternatives considered | Evidence |
|---|---|---|---|
| Japanese ASR (short clips, CPU) | SenseVoice Small int8 via sherpa-onnx | Parakeet ja (tie, heavier), ReazonSpeech k2 (Apache-2.0, −1.5 pt), Whisper small (worse, 7× slower), Moonshine ja (non-commercial) | [E] E-001 |
| Japanese ASR (noisy media, long-form) | not decided; candidates Qwen3-ASR-0.6B, Whisper large-v3-turbo on GPU | Haas-ja (GPU-only runtime) | [B] neosophie, Haas card → `research/speech-ai/asr-candidates.md` |
| Commercial ASR fallback | OpenAI `gpt-4o-mini-transcribe` ($0.003/min) behind OpenAI-compatible adapter | gpt-transcribe, Deepgram, Groq, Gemini transcribe | [V] prices; not run live (no key) |
| VAD / utterance cutting | Silero VAD (sherpa-onnx) | TEN VAD | [V] used in stream (E-003) |
| Media decoding | ffmpeg/ffprobe subprocess, container allow-list, `-protocol_whitelist file` | PyAV in-process | [V] |
| Subtitles | own SRT/VTT renderer from timed segments | — | [V] tests |
| Speaker diarization | not built | pyannote, Nemotron diarization | [H] |
| TTS | not built; Kokoro-82M (Apache-2.0, sherpa-onnx) first to test; VOICEVOX per-voice terms | OpenAI/Gemini/Azure TTS | [V] licences, quality unmeasured |

## Pronunciation
| Stage | Method | Evidence |
|---|---|---|
| v0 (built) | ASR → kana → mora alignment, typed issues | [E] E-002 strictness; sensitivity on learners unknown |
| v1 | phoneme-CTC posteriors + forced alignment (GOP), mora durations | [P]; model `japanese-hubert-base-phoneme-ctc-v4` (Apache-2.0) |
| v2 | F0 per mora vs dictionary accent (pyopenjtalk-plus) | [P]; Azure has no ja prosody [V] |
→ `research/pronunciation/assessment-approaches.md`

## Japanese language
| Need | Choice | Evidence |
|---|---|---|
| Tokenise, POS, lemma, conjugation, readings | Sudachi (SudachiPy 0.7 + core dict), split modes A/B/C | [V] built + tests |
| Furigana, romaji, mora split, numbers → kanji | own rules on Sudachi readings | [V] tests |
| JLPT level of words | not built; Waller lists are unofficial, CC-BY reported [H] → label as estimate | [H] |
| Grammar correction / explanation / naturalness / keigo | LLM (Claude default, adapter for others), with deterministic analysis as grounding | [P], prices [V] in `PROVIDER_COMPARISON.md` |
| Dictionary glosses | JMdict (EDRDG licence, attribution + share-alike) [H] | [H] verify before use |

## Tutor and personalisation
| Need | Choice |
|---|---|
| Review scheduling | keep backend SM-2; FSRS (py-fsrs, MIT) is a measured upgrade path [P] |
| Weakness detection | aggregate pronunciation issue types + JLPT attempt results per user, plain statistics [P] |
| Tutor dialogue | LLM with a structured learner profile (level, weak items, recent errors), not raw history [P] |

## Platform
FastAPI + Uvicorn (async; CPU work in threads), pydantic-settings, httpx, YAML registry,
in-process rate limiter and concurrency slots, JSON logs, Docker (classic builder). No queue/DB yet:
nothing long-running exists. Add a job queue only with long-media processing.
