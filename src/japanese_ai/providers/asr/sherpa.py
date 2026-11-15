"""Local speech recognition through sherpa-onnx (ONNX Runtime, CPU-friendly, no PyTorch).

One adapter covers several model families published for sherpa-onnx; the registry entry's
``config.family`` picks the loader.
"""

from __future__ import annotations

import asyncio
import threading
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from japanese_ai.providers.base import (
    SAMPLE_RATE,
    ASRProvider,
    AudioClip,
    ProviderError,
    ProviderUnavailable,
    Segment,
    TranscribeOptions,
    Transcription,
    Word,
)
from japanese_ai.services.speech.vad import split_speech

if TYPE_CHECKING:
    from japanese_ai.core.config import Settings
    from japanese_ai.model_registry.registry import ModelSpec

# family -> the model files it needs (keys of ``config.files``)
_REQUIRED_FILES = {
    "transducer": ("encoder", "decoder", "joiner", "tokens"),
    "sense_voice": ("model", "tokens"),
    "nemo_ctc": ("model", "tokens"),
    "moonshine_v2": ("encoder", "decoder", "tokens"),
}


class SherpaOnnxASR(ASRProvider):
    def __init__(self, spec: ModelSpec, settings: Settings) -> None:
        super().__init__(spec)
        config = spec.config
        self._family: str = config["family"]
        if self._family not in _REQUIRED_FILES:
            raise ValueError(f"{spec.id}: unknown sherpa-onnx family '{self._family}'")
        self._dir = settings.models_dir / config["dir"]
        self._files: dict[str, str] = config["files"]
        self._threads = int(config.get("num_threads", 2))
        self._language: str = config.get("language", "ja")
        # Recordings longer than this are cut at pauses first: these models are trained on
        # utterances of up to ~30 s and get slow and inaccurate beyond that.
        self._split_over_seconds = float(config.get("split_over_seconds", 20.0))
        self._vad_model = settings.models_dir / config.get("vad_model", "sherpa/silero_vad.onnx")
        self._recognizer: Any = None
        self._lock = threading.Lock()

    def _path(self, key: str) -> Path:
        return self._dir / self._files[key]

    def availability(self) -> tuple[bool, str | None]:
        if find_spec("sherpa_onnx") is None:
            return False, "python package 'sherpa-onnx' is not installed"
        missing = [key for key in _REQUIRED_FILES[self._family] if key not in self._files]
        if missing:
            return False, f"registry entry lacks files: {', '.join(missing)}"
        absent = [self._files[key] for key in _REQUIRED_FILES[self._family] if not self._path(key).is_file()]
        if absent:
            return False, f"model files not found under {self._dir}: {', '.join(absent)}"
        return True, None

    def _load(self) -> Any:
        import sherpa_onnx  # noqa: PLC0415 - optional dependency

        recognizer = sherpa_onnx.OfflineRecognizer
        common = {"tokens": str(self._path("tokens")), "num_threads": self._threads}
        if self._family == "transducer":
            return recognizer.from_transducer(
                encoder=str(self._path("encoder")),
                decoder=str(self._path("decoder")),
                joiner=str(self._path("joiner")),
                **common,
            )
        if self._family == "sense_voice":
            return recognizer.from_sense_voice(
                model=str(self._path("model")), language=self._language, use_itn=True, **common
            )
        if self._family == "nemo_ctc":
            return recognizer.from_nemo_ctc(model=str(self._path("model")), **common)
        return recognizer.from_moonshine_v2(
            encoder=str(self._path("encoder")), decoder=str(self._path("decoder")), **common
        )

    def _ensure_loaded(self) -> Any:
        if self._recognizer is None:
            usable, reason = self.availability()
            if not usable:
                raise ProviderUnavailable(reason or "unavailable", provider=self.spec.id)
            try:
                self._recognizer = self._load()
            except Exception as exc:  # the native loader raises plain RuntimeError
                raise ProviderUnavailable(f"failed to load model: {exc}", provider=self.spec.id) from exc
        return self._recognizer

    async def warm_up(self) -> None:
        await asyncio.to_thread(self._locked, self._ensure_loaded)

    async def transcribe(self, clip: AudioClip, options: TranscribeOptions) -> Transcription:
        return await asyncio.to_thread(self._locked, self._transcribe_sync, clip, options)

    def _locked(self, func: Any, *args: Any) -> Any:
        # One decode at a time per model: the recognizer is not documented as thread-safe.
        with self._lock:
            return func(*args)

    def _pieces(self, clip: AudioClip) -> list[tuple[float, np.ndarray]]:
        if clip.duration <= self._split_over_seconds:
            return [(0.0, clip.samples)]
        if self._vad_model.is_file():
            spans = split_speech(clip.samples, self._vad_model, max_speech_seconds=self._split_over_seconds)
            return [(span.start, span.samples) for span in spans]
        # No VAD model on disk: fall back to fixed windows. Words at the cuts may suffer.
        window = int(self._split_over_seconds * SAMPLE_RATE)
        return [
            (start / SAMPLE_RATE, clip.samples[start : start + window])
            for start in range(0, len(clip.samples), window)
        ]

    def _transcribe_sync(self, clip: AudioClip, options: TranscribeOptions) -> Transcription:
        recognizer = self._ensure_loaded()
        segments: list[Segment] = []
        try:
            for offset, samples in self._pieces(clip):
                stream = recognizer.create_stream()
                stream.accept_waveform(SAMPLE_RATE, samples)
                recognizer.decode_stream(stream)
                result = stream.result
                text = result.text.strip()
                if not text:
                    continue
                end = offset + len(samples) / SAMPLE_RATE
                words = _words(result, offset, end) if options.word_timestamps else ()
                segments.append(Segment(start=round(offset, 3), end=round(end, 3), text=text, words=words))
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"decoding failed: {exc}", provider=self.spec.id) from exc
        return Transcription(
            text="".join(segment.text for segment in segments),
            segments=tuple(segments),
            language=self._language,
        )


def _words(result: Any, offset: float, segment_end: float) -> tuple[Word, ...]:
    tokens = list(getattr(result, "tokens", None) or [])
    stamps = list(getattr(result, "timestamps", None) or [])
    if not tokens or len(tokens) != len(stamps):
        return ()
    words = []
    for index, (token, start) in enumerate(zip(tokens, stamps, strict=True)):
        end = stamps[index + 1] + offset if index + 1 < len(stamps) else segment_end
        words.append(Word(text=token, start=round(start + offset, 3), end=round(end, 3)))
    return tuple(words)
