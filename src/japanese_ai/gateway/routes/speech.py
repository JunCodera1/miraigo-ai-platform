from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import PlainTextResponse

from japanese_ai.core import errors
from japanese_ai.core.envelope import ApiResponse, success
from japanese_ai.core.errors import AppError
from japanese_ai.gateway.deps import ContainerDep, InferencePrincipalDep
from japanese_ai.gateway.routes.helpers import meta_of
from japanese_ai.gateway.schemas import (
    CountsOut,
    IssueOut,
    PronunciationOut,
    ScoresOut,
    SegmentOut,
    TranscriptionOut,
    WordOut,
    WordScoreOut,
)
from japanese_ai.pipelines import pronunciation
from japanese_ai.providers.base import TranscribeOptions
from japanese_ai.services.speech import subtitles
from japanese_ai.services.speech.audio import load_clip

router = APIRouter(prefix="/api/v1")

LIMITATIONS = [
    "Scores come from comparing a speech recogniser's output with the reference; they measure intelligibility, not native-likeness.",
    "Pitch accent and intonation are not assessed yet.",
    "The recogniser can occasionally correct a small mistake or mishear a correct word.",
]


async def _clip(container, file: UploadFile, max_seconds: float):
    s = container.settings
    return await load_clip(
        file.file,
        max_bytes=s.max_upload_bytes,
        max_seconds=max_seconds,
        temp_dir=s.temp_dir,
        ffmpeg=s.ffmpeg_path,
        ffprobe=s.ffprobe_path,
    )


@router.post(
    "/speech/transcribe",
    tags=["speech"],
    summary="Japanese speech to text, with timestamps; JSON, SRT or WebVTT",
    response_model=ApiResponse[TranscriptionOut],
    responses={200: {"content": {"text/plain": {}, "text/vtt": {}}}},
)
async def transcribe(
    request: Request,
    container: ContainerDep,
    _: InferencePrincipalDep,
    file: Annotated[UploadFile, File(description="Audio or video (wav, mp3, m4a, webm, ogg, mp4, ...)")],
    model: Annotated[str | None, Form(description="Registry model id; default routing when omitted")] = None,
    word_timestamps: Annotated[bool, Form(alias="wordTimestamps")] = False,
    response_format: Annotated[Literal["json", "srt", "vtt"], Form(alias="responseFormat")] = "json",
):
    clip, _info = await _clip(container, file, container.settings.max_audio_seconds)
    routed = await container.router.transcribe(
        clip, TranscribeOptions(language="ja", word_timestamps=word_timestamps), model=model
    )
    result = routed.value
    if response_format != "json":
        media = "text/vtt" if response_format == "vtt" else "application/x-subrip"
        return PlainTextResponse(
            subtitles.render(result.segments, response_format),
            media_type=f"{media}; charset=utf-8",
            headers={"X-Model": routed.model_id},
        )
    segments = [
        SegmentOut(
            start=s.start,
            end=s.end,
            text=s.text,
            words=[WordOut(text=w.text, start=w.start, end=w.end) for w in s.words]
            if word_timestamps
            else None,
        )
        for s in result.segments
    ]
    data = TranscriptionOut(
        text=result.text,
        language=result.language,
        duration_seconds=round(clip.duration, 3),
        segments=segments,
        meta=meta_of(routed),
    )
    return success(request, data)


@router.post(
    "/pronunciation/evaluate",
    tags=["pronunciation"],
    summary="Score a read-aloud recording against reference text",
)
async def evaluate(
    request: Request,
    container: ContainerDep,
    _: InferencePrincipalDep,
    file: Annotated[UploadFile, File(description="Recording of the learner reading the reference text")],
    reference_text: Annotated[str, Form(alias="referenceText", min_length=1, max_length=200)],
    model: Annotated[str | None, Form()] = None,
) -> ApiResponse[PronunciationOut]:
    reference_text = reference_text.strip()
    if not reference_text:
        raise AppError(errors.VALIDATION_FAILED, "referenceText is empty.", 422)
    clip, _info = await _clip(container, file, container.settings.max_pronunciation_audio_seconds)
    result = await pronunciation.evaluate(
        container.router, container.analyzer, clip, reference_text, model=model
    )
    sc = result.score
    data = PronunciationOut(
        method=pronunciation.METHOD,
        reference_text=result.reference_text,
        recognized_text=result.recognized_text,
        scores=ScoresOut(overall=sc.overall, accuracy=sc.accuracy, completeness=sc.completeness),
        counts=CountsOut(
            morae=sc.mora_count,
            matched=sc.matched,
            substituted=sc.substituted,
            omitted=sc.omitted,
            inserted=sc.inserted,
        ),
        speech_rate_morae_per_second=result.speech_rate_morae_per_second,
        duration_seconds=result.duration_seconds,
        words=[
            WordScoreOut(
                text=w.text,
                expected=w.expected,
                heard=w.heard,
                status=w.status,
                issues=[
                    IssueOut(type=i.type, expected=i.expected, heard=i.heard, message=i.message)
                    for i in w.issues
                ],
            )
            for w in sc.words
        ],
        limitations=LIMITATIONS,
        meta=meta_of(result.routed),
    )
    return success(request, data)
