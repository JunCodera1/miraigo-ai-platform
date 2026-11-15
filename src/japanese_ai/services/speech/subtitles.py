"""Subtitle rendering from timed segments (SubRip and WebVTT)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from japanese_ai.providers.base import Segment

SubtitleFormat = Literal["srt", "vtt"]


def _timestamp(seconds: float, separator: str) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _clean(text: str) -> str:
    # A cue ends at a blank line, and "-->" inside cue text breaks WebVTT parsers.
    return " ".join(text.split()).replace("-->", "->")


def render(segments: Iterable[Segment], fmt: SubtitleFormat) -> str:
    cues = [segment for segment in segments if segment.text.strip()]
    separator = "," if fmt == "srt" else "."
    lines: list[str] = ["WEBVTT", ""] if fmt == "vtt" else []
    for index, segment in enumerate(cues, start=1):
        end = max(segment.end, segment.start + 0.001)
        if fmt == "srt":
            lines.append(str(index))
        lines.append(f"{_timestamp(segment.start, separator)} --> {_timestamp(end, separator)}")
        lines.append(_clean(segment.text))
        lines.append("")
    return "\n".join(lines)
