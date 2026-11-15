"""Turns an uploaded media file into a validated 16 kHz mono clip.

Uploads are untrusted. Nothing here believes the file name or the declared content type:
ffprobe decides what the file is, only ordinary audio/video containers are accepted, and ffmpeg
is restricted to reading the one local file it is given.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import numpy as np

from japanese_ai.core import errors
from japanese_ai.core.errors import AppError
from japanese_ai.providers.base import SAMPLE_RATE, AudioClip

# Containers a phone, a browser or a learner's own file can reasonably produce. Playlist and
# script-like formats (HLS, concat, ...) are excluded: they can make ffmpeg open other files.
ALLOWED_FORMATS = frozenset(
    {
        "wav",
        "w64",
        "aiff",
        "mp3",
        "flac",
        "ogg",
        "aac",
        "amr",
        "caf",
        "mov",
        "mp4",
        "m4a",
        "3gp",
        "3g2",
        "matroska",
        "webm",
    }
)
MIN_SECONDS = 0.1
_PROBE_TIMEOUT = 15.0
_COPY_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class ProbeInfo:
    format_names: tuple[str, ...]
    codec: str
    has_video: bool


async def stage_upload(source: BinaryIO, max_bytes: int, temp_dir: Path | None) -> Path:
    """Copy an upload to a private temp file, refusing to write more than ``max_bytes``."""
    descriptor, name = tempfile.mkstemp(prefix="jai-upload-", dir=temp_dir)  # mode 0600
    path = Path(name)
    written = 0
    try:
        with os.fdopen(descriptor, "wb") as target:
            while chunk := await asyncio.to_thread(source.read, _COPY_CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    raise AppError(
                        errors.FILE_TOO_LARGE,
                        f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.",
                        413,
                    )
                target.write(chunk)
    except BaseException:
        discard(path)
        raise
    if written == 0:
        discard(path)
        raise AppError(errors.AUDIO_EMPTY, "The uploaded file is empty.", 400)
    return path


def discard(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


async def _run(*command: str, timeout: float) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise AppError(errors.AUDIO_INVALID, "The file could not be processed in time.", 400) from None
    return process.returncode or 0, stdout, stderr


async def probe(path: Path, ffprobe: str = "ffprobe") -> ProbeInfo:
    code, stdout, _ = await _run(
        ffprobe,
        "-v", "error",
        "-protocol_whitelist", "file",
        "-show_entries", "format=format_name:stream=codec_type,codec_name",
        "-of", "json",
        str(path),
        timeout=_PROBE_TIMEOUT,
    )  # fmt: skip
    if code != 0:
        raise AppError(errors.AUDIO_INVALID, "The file is not a readable audio or video file.", 400)
    try:
        info = json.loads(stdout)
        format_names = tuple(str(info["format"]["format_name"]).split(","))
        streams = info.get("streams", [])
    except (ValueError, KeyError, TypeError):
        raise AppError(errors.AUDIO_INVALID, "The file is not a readable audio or video file.", 400) from None

    if not ALLOWED_FORMATS.intersection(format_names):
        raise AppError(errors.AUDIO_INVALID, f"Unsupported media format: {format_names[0]}.", 400)
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not audio:
        raise AppError(errors.AUDIO_INVALID, "The file contains no audio track.", 400)
    return ProbeInfo(
        format_names=format_names,
        codec=str(audio[0].get("codec_name", "unknown")),
        has_video=any(stream.get("codec_type") == "video" for stream in streams),
    )


async def decode(path: Path, max_seconds: float, ffmpeg: str = "ffmpeg") -> AudioClip:
    """Decode the first audio track. Fails if it runs longer than ``max_seconds``."""
    # Some recorders (browser WebM) write no duration, so length is checked on the decoded
    # samples; ``-t`` only stops ffmpeg from decoding hours of audio we would then reject.
    cap = max_seconds + 1.0
    code, stdout, _ = await _run(
        ffmpeg,
        "-nostdin", "-v", "error",
        "-protocol_whitelist", "file,pipe",
        "-i", str(path),
        "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-t", f"{cap:.3f}",
        "-f", "f32le", "pipe:1",
        timeout=max(30.0, cap),
    )  # fmt: skip
    if code != 0:
        raise AppError(errors.AUDIO_INVALID, "The audio track could not be decoded.", 400)

    samples = np.frombuffer(stdout, dtype="<f4")
    clip = AudioClip(samples=samples)
    if clip.duration < MIN_SECONDS:
        raise AppError(errors.AUDIO_EMPTY, "The recording is too short to process.", 400)
    if clip.duration > max_seconds:
        raise AppError(
            errors.AUDIO_TOO_LONG,
            f"The recording is longer than the {max_seconds:g} second limit for this endpoint.",
            413,
        )
    return clip


async def load_clip(
    source: BinaryIO,
    *,
    max_bytes: int,
    max_seconds: float,
    temp_dir: Path | None = None,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> tuple[AudioClip, ProbeInfo]:
    """Stage, inspect and decode an upload. The staged copy is always deleted."""
    path = await stage_upload(source, max_bytes, temp_dir)
    try:
        info = await probe(path, ffprobe)
        clip = await decode(path, max_seconds, ffmpeg)
    finally:
        discard(path)
    return clip, info
