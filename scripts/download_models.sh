#!/usr/bin/env bash
# Download the local speech models used by the default registry.
#   scripts/download_models.sh [models_dir]     (default: ~/.local/share/japanese-ai-platform/models)
set -euo pipefail
DEST="${1:-$HOME/.local/share/japanese-ai-platform/models}/sherpa"
BASE=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models
mkdir -p "$DEST"
fetch() {
  local name="$1"
  if [ -d "$DEST/$name" ]; then echo "have $name"; return; fi
  echo "downloading $name"
  curl -fL --retry 3 "$BASE/$name.tar.bz2" | tar -xj -C "$DEST"
}
# primary (original multilingual build; the 2025-09-09 archive is a Cantonese fine-tune - do not use)
fetch sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17
# fallbacks
fetch sherpa-onnx-zipformer-ja-reazonspeech-2024-08-01
if [ "${WITH_PARAKEET:-0}" = "1" ]; then fetch sherpa-onnx-nemo-parakeet-tdt_ctc-0.6b-ja-35000-int8; fi
[ -f "$DEST/silero_vad.onnx" ] || curl -fL --retry 3 -o "$DEST/silero_vad.onnx" "$BASE/silero_vad.onnx"
du -sh "$DEST"/*
