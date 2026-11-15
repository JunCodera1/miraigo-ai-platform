"""Public request/response schemas (camelCase on the wire)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from japanese_ai.core.envelope import CamelModel


class ExecutionMeta(CamelModel):
    model: str = Field(description="Registry id of the model that produced the result")
    provider: str
    processing_ms: int
    estimated_cost_usd: float
    fallback_used: bool


class WordOut(CamelModel):
    text: str
    start: float
    end: float


class SegmentOut(CamelModel):
    start: float
    end: float
    text: str
    words: list[WordOut] | None = None


class TranscriptionOut(CamelModel):
    text: str
    language: str | None
    duration_seconds: float
    segments: list[SegmentOut]
    meta: ExecutionMeta


class FuriganaOut(CamelModel):
    text: str
    reading: str | None


class TokenOut(CamelModel):
    surface: str
    lemma: str
    reading: str | None = Field(description="Hiragana, as pronounced")
    romaji: str | None
    pos: str
    pos_detail: list[str]
    conjugation_type: str | None
    conjugation_form: str | None
    conjugation_form_en: str | None
    furigana: list[FuriganaOut] | None
    start: int
    end: int
    is_word: bool
    is_oov: bool


class AnalyzeIn(CamelModel):
    text: str = Field(min_length=1, examples=["私は毎日日本語を勉強しています。"])
    split_mode: Literal["A", "B", "C"] = Field(default="C", description="A = shortest units, C = longest")


class AnalyzeOut(CamelModel):
    text: str
    reading: str = Field(description="Whole sentence in hiragana")
    romaji: str
    tokens: list[TokenOut]


class IssueOut(CamelModel):
    type: str
    expected: str | None
    heard: str | None
    message: str


class WordScoreOut(CamelModel):
    text: str
    expected: str
    heard: str
    status: Literal["ok", "partial", "missed"]
    issues: list[IssueOut]


class ScoresOut(CamelModel):
    overall: int = Field(ge=0, le=100)
    accuracy: int = Field(ge=0, le=100)
    completeness: int = Field(ge=0, le=100)


class CountsOut(CamelModel):
    morae: int
    matched: int
    substituted: int
    omitted: int
    inserted: int


class PronunciationOut(CamelModel):
    method: str
    reference_text: str
    recognized_text: str
    scores: ScoresOut
    counts: CountsOut
    speech_rate_morae_per_second: float | None
    duration_seconds: float
    words: list[WordScoreOut]
    limitations: list[str]
    meta: ExecutionMeta


class ModelOut(CamelModel):
    id: str
    capability: str
    provider: str
    deployment: str
    languages: list[str]
    license: str
    source: str
    description: str
    enabled: bool
    available: bool
    unavailable_reason: str | None
    features: dict[str, object]
    routing_role: Literal["primary", "fallback", "none"] = Field(
        description="Role in the transcription route"
    )
    routing_roles: dict[str, Literal["primary", "fallback", "none"]] = Field(description="Role per route")


class HealthOut(CamelModel):
    status: Literal["ok", "degraded"]
    version: str
    env: str
    capabilities: dict[str, bool]
