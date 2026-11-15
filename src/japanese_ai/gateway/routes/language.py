from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from japanese_ai.core import errors
from japanese_ai.core.envelope import ApiResponse, success
from japanese_ai.core.errors import AppError
from japanese_ai.gateway.deps import ContainerDep, PrincipalDep
from japanese_ai.gateway.schemas import AnalyzeIn, AnalyzeOut, FuriganaOut, TokenOut
from japanese_ai.services.language import kana

router = APIRouter(prefix="/api/v1/language", tags=["language"])


@router.post("/analyze", summary="Tokens, readings, furigana, romaji and conjugation (deterministic)")
async def analyze(
    request: Request, body: AnalyzeIn, container: ContainerDep, _: PrincipalDep
) -> ApiResponse[AnalyzeOut]:
    text = body.text.strip()
    if len(text) > container.settings.max_text_chars:
        raise AppError(
            errors.VALIDATION_FAILED,
            f"Text is longer than {container.settings.max_text_chars} characters.",
            422,
        )
    if not text:
        raise AppError(errors.VALIDATION_FAILED, "Text is empty.", 422)
    tokens = await asyncio.to_thread(container.analyzer.tokenize, text, body.split_mode)
    out = [
        TokenOut(
            surface=t.surface,
            lemma=t.lemma,
            reading=t.reading_hiragana,
            romaji=t.romaji,
            pos=t.pos,
            pos_detail=list(t.pos_detail),
            conjugation_type=t.conjugation_type,
            conjugation_form=t.conjugation_form,
            conjugation_form_en=t.conjugation_form_en,
            furigana=[FuriganaOut(text=p.text, reading=p.reading) for p in t.furigana]
            if t.furigana
            else None,
            start=t.start,
            end=t.end,
            is_word=t.is_word,
            is_oov=t.is_oov,
        )
        for t in tokens
    ]
    reading_kata = "".join(t.reading or ("" if t.is_word else t.surface) for t in tokens)
    words_romaji = " ".join(t.romaji for t in tokens if t.is_word and t.romaji)
    return success(
        request,
        AnalyzeOut(text=text, reading=kana.to_hiragana(reading_kata), romaji=words_romaji, tokens=out),
    )
