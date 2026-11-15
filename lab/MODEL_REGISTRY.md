# Model Registry (human view)

Source of truth for the running service: `src/japanese_ai/model_registry/models.yaml`.
This page adds the why. Quality numbers: `EXPERIMENT_RESULTS.md`.

| id | Task | Runtime | Licence | Role | Why |
|---|---|---|---|---|---|
| `sensevoice-small-int8` | ASR ja | sherpa-onnx, CPU | FunASR Model License v1.1 (custom: attribution + keep model name; no explicit commercial clause) [V] | **transcription primary**, pronunciation fallback | best CER tie, 2× faster and ⅓ RAM of Parakeet (E-001); punctuation |
| `reazonspeech-zipformer-ja` | ASR ja | sherpa-onnx | Apache-2.0 | **pronunciation primary**, transcription fallback 1 | Apache-2.0, smallest; same kana CER as SenseVoice; highest E-002 (90/100 ≥ 90) |
| `parakeet-tdt-ctc-0.6b-ja` | ASR ja | sherpa-onnx | CC-BY-4.0 | fallback 2 | ties best CER; 970 MB RAM |
| `openai-gpt-4o-mini-transcribe` | ASR | OpenAI API | commercial | fallback 3 (needs `OPENAI_API_KEY`) | $0.003/min [V]; untested live (no key) |
| `whisper-small-ct2` | ASR multi | faster-whisper | MIT | enabled, not routed | 13.5 % CER, 7× slower; keep for non-Japanese audio |
| `moonshine-base-ja` | ASR ja | sherpa-onnx | Moonshine Community (**non-commercial**) [V] | disabled | licence + worst Japanese CER among small models |
| `legacy-voiceai` | ASR+LID | HTTP to old prototype | internal | disabled | baseline only (34.6 % CER) |
| Silero VAD | VAD | sherpa-onnx | MIT | used by stream + long audio | 0.6 MB |
| Sudachi + SudachiDict-core | morphology | SudachiPy | Apache-2.0 [H: dict licence per WorksApplications] | always | deterministic readings/POS/conjugation |

Candidates not yet evaluated (shortlist, in priority order):
1. Qwen3-ASR-0.6B int8 (Apache-2.0, sherpa-onnx 879 MB) — best in third-party media benchmark [B]; check CPU speed.
2. Haas-ja-v1.0 (Apache-2.0) — 6.12 % CER claim [B]; official runtime GPU-only; look for ONNX ports.
3. kotoba-whisper v2 (Apache/MIT) — needs GPU to be practical; poor on conversation [B].
4. Phoneme CTC for pronunciation v1: `prj-beatrice/japanese-hubert-base-phoneme-ctc-v4` (Apache-2.0, ONNX port exists).
5. TTS: Kokoro-82M (Apache-2.0) via sherpa-onnx; VOICEVOX (per-voice terms).
