"""Pronunciation evaluation pipeline.

1. audio is already decoded and validated by the gateway
2. reference text -> words -> morae (Sudachi + kana rules)
3. speech recognition through the capability router
4. recognised text -> morae
5. mora alignment and typed issues
6. structured feedback
"""

from __future__ import annotations

from dataclasses import dataclass

from japanese_ai.core import errors
from japanese_ai.core.errors import AppError
from japanese_ai.orchestration.router import CapabilityRouter
from japanese_ai.providers.base import AudioClip, RoutedResult, TranscribeOptions, Transcription
from japanese_ai.services.language import kana
from japanese_ai.services.language.analyzer import JapaneseAnalyzer
from japanese_ai.services.pronunciation.scoring import PronunciationScore, score

METHOD = "asr_alignment_v0"
SILENCE_RMS = 0.003


@dataclass
class PronunciationResult:
    reference_text: str
    recognized_text: str
    score: PronunciationScore
    speech_rate_morae_per_second: float | None
    duration_seconds: float
    routed: RoutedResult[Transcription]


def reference_units(analyzer: JapaneseAnalyzer, text: str) -> list[tuple[str, list[str]]]:
    units = [(token.surface, morae) for token, morae in analyzer.reading_units(text)]
    if not units:
        raise AppError(errors.TEXT_NOT_JAPANESE, "The reference text has no readable Japanese.", 422)
    return units


def heard_morae(analyzer: JapaneseAnalyzer, text: str) -> list[str]:
    return [mora for _, morae in analyzer.reading_units(text) for mora in morae]


async def evaluate(
    router: CapabilityRouter,
    analyzer: JapaneseAnalyzer,
    clip: AudioClip,
    reference_text: str,
    *,
    model: str | None = None,
) -> PronunciationResult:
    reference = reference_units(analyzer, reference_text)
    if clip.rms < SILENCE_RMS:
        raise AppError(errors.AUDIO_EMPTY, "No speech was detected in the recording.", 422)

    routed = await router.transcribe(
        clip, TranscribeOptions(language="ja"), model=model, route="pronunciation"
    )
    recognized = routed.value.text
    heard = heard_morae(analyzer, recognized)
    result = score(reference, heard)

    spoken = len(heard)
    speech_time = _speech_span(routed.value) or clip.duration
    rate = round(spoken / speech_time, 2) if spoken and speech_time > 0 else None
    return PronunciationResult(
        reference_text=reference_text,
        recognized_text=recognized,
        score=result,
        speech_rate_morae_per_second=rate,
        duration_seconds=round(clip.duration, 3),
        routed=routed,
    )


def _speech_span(transcription: Transcription) -> float | None:
    if not transcription.segments:
        return None
    return transcription.segments[-1].end - transcription.segments[0].start


__all__ = ["METHOD", "PronunciationResult", "evaluate", "heard_morae", "kana", "reference_units"]
