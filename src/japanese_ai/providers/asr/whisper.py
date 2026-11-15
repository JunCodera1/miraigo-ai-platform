"""Local Whisper-family speech recognition through faster-whisper (CTranslate2).

Covers every Whisper checkpoint converted to CTranslate2, including Japanese fine-tunes such as
kotoba-whisper. Weights are downloaded from Hugging Face on first load unless they are already
under ``<models_dir>/faster-whisper``.
"""

from __future__ import annotations

import asyncio
import threading
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any

from japanese_ai.providers.base import (
    ASRProvider,
    AudioClip,
    ProviderError,
    ProviderUnavailable,
    Segment,
    TranscribeOptions,
    Transcription,
    Word,
)

if TYPE_CHECKING:
    from japanese_ai.core.config import Settings
    from japanese_ai.model_registry.registry import ModelSpec


class FasterWhisperASR(ASRProvider):
    def __init__(self, spec: ModelSpec, settings: Settings) -> None:
        super().__init__(spec)
        config = spec.config
        self._model_name: str = config["model"]
        self._device: str = config.get("device", "cpu")
        self._compute_type: str = config.get("compute_type", "int8")
        self._cpu_threads = int(config.get("cpu_threads", 4))
        self._beam_size = int(config.get("beam_size", 5))
        self._vad_filter = bool(config.get("vad_filter", True))
        self._local_only = bool(config.get("local_files_only", False))
        self._download_root = settings.models_dir / "faster-whisper"
        self._model: Any = None
        self._lock = threading.Lock()

    def availability(self) -> tuple[bool, str | None]:
        if find_spec("faster_whisper") is None:
            return False, "python package 'faster-whisper' is not installed"
        return True, None

    def _ensure_loaded(self) -> Any:
        if self._model is None:
            usable, reason = self.availability()
            if not usable:
                raise ProviderUnavailable(reason or "unavailable", provider=self.spec.id)
            from faster_whisper import WhisperModel  # noqa: PLC0415 - optional dependency

            try:
                self._model = WhisperModel(
                    self._model_name,
                    device=self._device,
                    compute_type=self._compute_type,
                    cpu_threads=self._cpu_threads,
                    download_root=str(self._download_root),
                    local_files_only=self._local_only,
                )
            except Exception as exc:
                raise ProviderUnavailable(f"failed to load model: {exc}", provider=self.spec.id) from exc
        return self._model

    async def warm_up(self) -> None:
        await asyncio.to_thread(self._locked, self._ensure_loaded)

    async def transcribe(self, clip: AudioClip, options: TranscribeOptions) -> Transcription:
        return await asyncio.to_thread(self._locked, self._transcribe_sync, clip, options)

    def _locked(self, func: Any, *args: Any) -> Any:
        with self._lock:
            return func(*args)

    def _transcribe_sync(self, clip: AudioClip, options: TranscribeOptions) -> Transcription:
        model = self._ensure_loaded()
        try:
            raw_segments, info = model.transcribe(
                clip.samples,
                language=options.language,
                beam_size=self._beam_size,
                vad_filter=self._vad_filter,
                word_timestamps=options.word_timestamps,
                # Each window is decoded on its own: carrying text forward is what makes
                # Whisper repeat itself over silence.
                condition_on_previous_text=False,
            )
            segments = []
            for raw in raw_segments:  # a generator: decoding happens here
                text = raw.text.strip()
                if not text:
                    continue
                words = tuple(
                    Word(text=word.word.strip(), start=round(word.start, 3), end=round(word.end, 3))
                    for word in (raw.words or [])
                )
                segments.append(
                    Segment(start=round(raw.start, 3), end=round(raw.end, 3), text=text, words=words)
                )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"decoding failed: {exc}", provider=self.spec.id) from exc

        language = info.language
        joiner = "" if language in {"ja", "zh", "yue"} else " "
        return Transcription(
            text=joiner.join(segment.text for segment in segments),
            segments=tuple(segments),
            language=language,
            language_probability=round(float(info.language_probability), 4),
        )
