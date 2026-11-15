# Japanese ASR candidates — evidence (2026-11-12)

Raw evidence behind the ASR choice. Conclusions live in `AI_TECHNOLOGY_ATLAS.md`; measured
numbers from this machine live in `EXPERIMENT_RESULTS.md`.
Labels: [V] fetched/read this session, [B] third-party benchmark (not reproduced), [H] recall, unverified.

## 1. Open models — licence, size, activity [V: Hugging Face API, 2026-11-12]

| Model | Licence | Repo size | HF downloads/mo | Notes |
|---|---|---|---|---|
| openai/whisper-large-v3 | Apache-2.0 | (multi-format) | 3.49M | multilingual reference |
| openai/whisper-large-v3-turbo | MIT | 1.6 GB | 4.97M | 809M params [H] |
| Systran/faster-whisper-{tiny,base,small} | MIT | 78 / 148 / 486 MB | 2.4M / 2.3M / 5.9M | CTranslate2 conversions |
| deepdml/faster-whisper-large-v3-turbo-ct2 | MIT | 1.6 GB | 418k | CT2 turbo |
| kotoba-tech/kotoba-whisper-v2.0(-faster) | Apache-2.0 (faster: MIT) | 1.5 GB | 23k / 12k | Japanese distil-large-v3 |
| reazon-research/reazonspeech-k2-v2 | Apache-2.0 | 775 MB | n/a | Zipformer transducer, ONNX, CPU-friendly |
| reazon-research/reazonspeech-nemo-v2 | Apache-2.0 | 2.5 GB | 3.5k | FastConformer RNN-T, needs NeMo/torch |
| reazon-research/reazonspeech-espnet-v2 | Apache-2.0 | 823 MB | 81 | slow (RTF 0.589 on RTX 5090 [B]) |
| nvidia/parakeet-tdt_ctc-0.6b-ja | CC-BY-4.0 | 2.5 GB | 7.7k | sherpa-onnx int8 export exists (489 MB) |
| FunAudioLLM/SenseVoiceSmall | FunASR Model Open Source License v1.1 [V]: use/modify/share, must attribute and keep model names, no explicit commercial clause | 944 MB | 27k | owner review (D-012) |
| Qwen/Qwen3-ASR-1.7B / 0.6B | Apache-2.0 | 4.7 / 1.9 GB | 1.63M / 535k | released 2026-01; sherpa-onnx int8 of 0.6B = 879 MB |
| third-intelligence/Haas-ja-v1.0 | Apache-2.0 | n/a | 3.7k | 615.8M params; official runtime **Linux + NVIDIA GPU only** |
| UsefulSensors/moonshine-{tiny,base}-ja | Moonshine Community License — **non-commercial** for non-English models [V: LICENSE file] | n/a | 1.1k / 153 | 48 / 104 MB quantized in sherpa-onnx |

Runtime projects [V: GitHub API, 2026-11-12]: SYSTRAN/faster-whisper MIT, 26.7k★, pushed 2026-11-12 ·
OpenNMT/CTranslate2 MIT, pushed 2026-11-10 · k2-fsa/sherpa-onnx Apache-2.0, 15.9k★, pushed 2026-11-12 ·
snakers4/silero-vad MIT, pushed 2026-10-22. All actively maintained.

## 2. Japanese-capable archives in the sherpa-onnx `asr-models` release [V: GitHub API]

| Archive | Size |
|---|---|
| sherpa-onnx-zipformer-ja-reazonspeech-2024-08-01 | 713 MB (fp32 + int8) |
| sherpa-onnx-zipformer-ja-en-reazonspeech-2025-01-17 | 438 MB |
| sherpa-onnx-nemo-parakeet-tdt_ctc-0.6b-ja-35000-int8 | 489 MB |
| sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17 | 163 MB — the original multilingual model (use this) |
| sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09 | 166 MB — **Cantonese fine-tune (WSYue), not for Japanese** [E] |
| sherpa-onnx-moonshine-tiny-ja-quantized-2026-02-27 / base-ja | 48 / 104 MB |
| sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25 | 879 MB |
| sherpa-onnx-streaming-zipformer-ar_en_id_ja_ru_th_vi_zh-2025-02-10 | 259 MB (true streaming, multilingual incl. ja + vi) |
| sherpa-onnx-whisper-{tiny,base,small,turbo} | 116 / 208 / 639 / 564 MB |
| silero_vad.onnx / ten-vad.onnx | 0.6 / 0.3 MB |

Download base: `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/<archive>.tar.bz2`.

## 3. Third-party benchmarks

### 3a. Neosophie, "Best Japanese ASR Models 2026" [B]
https://neosophie.com/en/blog/20260226-japanese-asr-benchmark (shown date 2026-05-01; fetched 2026-11-12).
20 clips × ~29 s (≈10 min) of **real broadcast/media audio** (news, variety, drama/anime, overlapping speech).
RTX 5090. Corpus-level CER after NFKC + removal of separators/punctuation/symbols.

| Model | CER | RTF |
|---|---|---|
| Qwen3-ASR-1.7B | 0.140 | 0.036 |
| Whisper large-v3-turbo | 0.184 | 0.013 |
| Voxtral-mini-4b-realtime | 0.212 | 0.209 |
| Granite-speech-4.1-2b | 0.262 | 0.051 |
| Cohere transcribe | 0.297 | 0.063 |
| Parakeet-tdt-0.6b-v3 | 0.321 | 0.003 |
| ReazonSpeech nemo-v2 | 0.329 | 0.020 |
| ReazonSpeech k2-v2 | 0.445 | 0.027 |
| kotoba-whisper-v2.0 | 0.495 | 0.008 |

Reading: tiny sample, hard conversational media. It shows ReazonSpeech-trained models and kotoba-whisper
degrade on noisy/overlapping speech and drop utterance tails; Whisper and Qwen3 stay stable. It does **not**
tell us about short, clean, read-aloud learner audio — that is what our own experiment covers.

### 3b. Haas-ja-v1.0 developer benchmark [B, developer-reported]
https://huggingface.co/third-intelligence/Haas-ja-v1.0 · https://github.com/third-intelligence/Haas-ASR
`asr-ja-bench` v1.1: JSUT basic5000, JVNV, TEDxJP-10K, FLEURS, SpeechBSD (18,318 utterances, 23.38 h).
Weighted strict CER: Haas-ja 6.12 %, GPT-Transcribe 6.07 %; Parakeet ≈ 1.1 points worse than Haas.
Per-model table is published only as an image (not readable here). CER normalised with `jacer`
(strict / flex / kana variants; not on PyPI). Limits: offline only, omits fillers, no CPU/macOS support.

### 3c. What these mean for a learner-speech platform
- No public benchmark covers **non-native learner speech**; every number above is native speech.
- Media-audio robustness (3a) matters for the multimedia/subtitle feature, not for read-aloud practice.
- A model that "cleans up" speech (drops fillers, fixes errors) is good for subtitles and **bad** for
  pronunciation assessment (see `../pronunciation/assessment-approaches.md`).

## 4. Legacy prototype (`miraigo-ai-server`, port 8000) [V: code read]
Source: https://github.com/JunCodera1/speech-language-model (cloned read-only to
`~/.local/share/japanese-ai-platform/reference/`). ECAPA-TDNN 5-language ID trained with SpeechBrain +
`openai/whisper-base` through `transformers` on CPU. The trained LID checkpoint (`results/`) is git-ignored
and exists only inside the Docker image. Train/dev/test split is random per file (80/10/10), so the README's
98.03 % LID accuracy may be optimistic if speakers repeat across splits [H]. No transcription accuracy was
ever measured for it.
