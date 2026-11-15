"""Real-model tests. Skipped unless the model files are on disk (scripts/download_models.sh)."""

import asyncio
import subprocess

import numpy as np
import pytest

from japanese_ai.model_registry.registry import ModelRegistry
from japanese_ai.providers.base import AudioClip, TranscribeOptions
from japanese_ai.providers.factory import ProviderPool
from tests.conftest import MODELS_DIR, make_settings

SENSEVOICE = MODELS_DIR / "sherpa" / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
JA_WAV = SENSEVOICE / "test_wavs" / "ja.wav"

pytestmark = [
    pytest.mark.models,
    pytest.mark.skipif(not JA_WAV.is_file(), reason="local models not downloaded"),
]


def load(path):
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"],
        capture_output=True,
        check=True,
    ).stdout
    return AudioClip(samples=np.frombuffer(out, dtype="<f4"))


@pytest.mark.parametrize("model_id", ["sensevoice-small-int8", "reazonspeech-zipformer-ja"])
def test_real_model_transcribes_japanese(model_id):
    settings = make_settings(models_dir=MODELS_DIR)
    provider = ProviderPool(settings).get(ModelRegistry.load().get(model_id))
    if not provider.availability()[0]:
        pytest.skip(provider.availability()[1])
    result = asyncio.run(provider.transcribe(load(JA_WAV), TranscribeOptions(word_timestamps=True)))
    # Reference: うちの中学は弁当制で持っていけない場合は、五十円の学校販売のパンを買う。
    for fragment in ("中学", "弁当", "学校販売", "パン"):
        assert fragment in result.text
    assert result.segments and result.segments[0].end > 5
