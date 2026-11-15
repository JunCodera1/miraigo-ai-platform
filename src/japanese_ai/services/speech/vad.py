"""Voice activity detection (Silero VAD through sherpa-onnx).

Used to cut long recordings into utterances before recognition, and to find utterance
boundaries in a live audio stream. sherpa-onnx is an optional dependency, so it is imported
lazily.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from japanese_ai.providers.base import SAMPLE_RATE


@dataclass(frozen=True)
class SpeechSpan:
    start: float  # seconds from the beginning of the audio fed so far
    samples: np.ndarray

    @property
    def end(self) -> float:
        return self.start + len(self.samples) / SAMPLE_RATE


class VoiceActivityDetector:
    """Feed audio in any chunk size; completed speech spans come out as they close."""

    def __init__(
        self,
        model_path: Path,
        *,
        min_silence_seconds: float = 0.35,
        min_speech_seconds: float = 0.2,
        max_speech_seconds: float = 20.0,
        threshold: float = 0.5,
    ) -> None:
        import sherpa_onnx  # noqa: PLC0415 - optional dependency

        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(model_path)
        config.silero_vad.threshold = threshold
        config.silero_vad.min_silence_duration = min_silence_seconds
        config.silero_vad.min_speech_duration = min_speech_seconds
        config.silero_vad.max_speech_duration = max_speech_seconds
        config.sample_rate = SAMPLE_RATE
        self._window = config.silero_vad.window_size
        self._vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=max_speech_seconds * 3)
        self._pending = np.zeros(0, dtype=np.float32)

    @property
    def speech_in_progress(self) -> bool:
        return bool(self._vad.is_speech_detected())

    def feed(self, samples: np.ndarray) -> Iterator[SpeechSpan]:
        self._pending = np.concatenate([self._pending, samples.astype(np.float32, copy=False)])
        offset = 0
        while len(self._pending) - offset >= self._window:
            self._vad.accept_waveform(self._pending[offset : offset + self._window])
            offset += self._window
            yield from self._drain()
        self._pending = self._pending[offset:]

    def finish(self) -> Iterator[SpeechSpan]:
        """Close any open span. Call once, when no more audio is coming."""
        if len(self._pending) > 0:
            padded = np.zeros(self._window, dtype=np.float32)
            padded[: len(self._pending)] = self._pending
            self._vad.accept_waveform(padded)
            self._pending = np.zeros(0, dtype=np.float32)
        self._vad.flush()
        yield from self._drain()

    def _drain(self) -> Iterator[SpeechSpan]:
        while not self._vad.empty():
            front = self._vad.front
            yield SpeechSpan(
                start=front.start / SAMPLE_RATE, samples=np.asarray(front.samples, dtype=np.float32)
            )
            self._vad.pop()


def split_speech(samples: np.ndarray, model_path: Path, **kwargs: float) -> list[SpeechSpan]:
    """Cut a whole recording into speech spans."""
    detector = VoiceActivityDetector(model_path, **kwargs)
    spans = list(detector.feed(samples))
    spans.extend(detector.finish())
    return spans
