# Feature Catalog

Status: BUILT (code + tests + live check) · PARTIAL · PLANNED · IDEA. Value: H/M/L for learners.

| Domain | Feature | Status | Value | Where / next step |
|---|---|---|---|---|
| Speech | Japanese STT with segment/token timestamps | BUILT | H | `/speech/transcribe` |
| Speech | SRT / WebVTT subtitles | BUILT | M | `responseFormat` |
| Speech | Live utterance transcription | BUILT | M | `WS /speech/stream` |
| Speech | Model fallback chain + per-request model choice | BUILT | — | router |
| Speech | Commercial ASR fallback | PARTIAL | M | adapter tested with mock; needs key + live check |
| Speech | Speaker diarization | IDEA | L | |
| Speech | TTS for examples (pre-generated, cached) | PLANNED | H | Kokoro / VOICEVOX eval |
| Pronunciation | Mora-level feedback vs reference (v0) | BUILT | H | `/pronunciation/evaluate` |
| Pronunciation | Speaking rate (morae/s) | BUILT | M | |
| Pronunciation | Acoustic GOP per mora, durations (v1) | PLANNED | H | phoneme CTC model |
| Pronunciation | Pitch-accent feedback (v2) | PLANNED | H | F0 + pyopenjtalk accent |
| Pronunciation | Shadowing mode (timing vs native audio) | IDEA | M | needs v1 alignment |
| Language | Tokens, POS, lemma, conjugation form | BUILT | H | `/language/analyze` |
| Language | Furigana, hiragana reading, romaji | BUILT | H | |
| Language | Grammar correction + explanation | PLANNED | H | LLM capability (see architecture) |
| Language | Vocabulary/kanji explanation in context | PLANNED | H | LLM + dictionary |
| Language | JLPT level estimate per word/sentence | PLANNED | M | unofficial lists → label as estimate |
| Language | Politeness/keigo detection & rewrite | PLANNED | M | Sudachi auxiliaries (rules) + LLM rewrite |
| Language | Translation (ja↔vi/en) with context | PLANNED | M | LLM |
| Multimedia | Upload video/audio → transcript | BUILT (≤120 s sync) | H | long files need job queue |
| Multimedia | Vocabulary list / exercises from media | PLANNED | H | transcript + analyzer + LLM |
| Multimedia | Video links | IDEA | M | copyright/ToS review first |
| Tutor | Conversation practice / role-play | PLANNED | H | LLM + learner profile |
| Tutor | Writing correction | PLANNED | H | same pipeline as grammar correction |
| Personalisation | Weak-sound profile from pronunciation issues | PLANNED | H | needs persisted events |
| Personalisation | Review scheduling | EXISTS in backend (SM-2) | H | FSRS upgrade optional |
