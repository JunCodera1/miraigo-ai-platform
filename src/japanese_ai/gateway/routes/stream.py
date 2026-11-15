"""Live transcription over WebSocket.

Protocol (docs/STREAMING.md):
  client -> {"type": "start", "token": "<access token>", "sampleRate": 16000}   (first message)
  client -> binary frames: little-endian PCM16 mono at ``sampleRate`` (16000 only, for now)
  client -> {"type": "stop"}
  server -> {"type": "ready"} | {"type": "speech_start"} |
            {"type": "segment", "start", "end", "text", "model"} | {"type": "done"} |
            {"type": "error", "errorCode", "message"}

Segments are produced per utterance: voice activity detection closes an utterance at a pause and
that utterance is recognised. Latency is therefore "end of utterance + decode time", not word by
word. Tokens go in the first message, not the URL, so they never land in access logs.
"""

from __future__ import annotations

import asyncio
import json

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from japanese_ai.core import errors
from japanese_ai.core.errors import AppError
from japanese_ai.core.logging import get_logger
from japanese_ai.gateway.container import Container
from japanese_ai.providers.base import SAMPLE_RATE, AudioClip, TranscribeOptions
from japanese_ai.services.speech.vad import VoiceActivityDetector

router = APIRouter()
log = get_logger("stream")
_START_TIMEOUT = 10.0
_MAX_FRAME_BYTES = 64 * 1024


async def _send_error(ws: WebSocket, code: str, message: str, close_code: int = 1008) -> None:
    try:
        await ws.send_json({"type": "error", "errorCode": code, "message": message})
        await ws.close(code=close_code)
    except (RuntimeError, WebSocketDisconnect):
        pass


@router.websocket("/api/v1/speech/stream")
async def stream(ws: WebSocket) -> None:
    container: Container = ws.app.state.container
    settings = container.settings
    origin = ws.headers.get("origin")
    if origin and origin not in settings.cors_origins:
        await ws.close(code=1008)
        return
    await ws.accept()

    try:
        first = await asyncio.wait_for(ws.receive_text(), timeout=_START_TIMEOUT)
        start = json.loads(first)
        if not isinstance(start, dict) or start.get("type") != "start":
            raise ValueError
    except (TimeoutError, ValueError, KeyError, WebSocketDisconnect, RuntimeError):
        await _send_error(ws, errors.BAD_REQUEST, 'First message must be {"type": "start", "token": ...}.')
        return

    try:
        token = start.get("token")
        principal = await container.authenticator.authenticate(
            f"Bearer {token}" if token else None, start.get("apiKey")
        )
        container.limiter.check(f"inference:{principal.label}", settings.inference_rate_limit_per_minute)
    except AppError as exc:
        await _send_error(ws, exc.code, exc.message)
        return

    if int(start.get("sampleRate", SAMPLE_RATE)) != SAMPLE_RATE:
        await _send_error(ws, errors.VALIDATION_FAILED, "Only 16000 Hz PCM16 mono is supported.", 1003)
        return
    vad_path = settings.models_dir / "sherpa" / "silero_vad.onnx"
    if not vad_path.is_file():
        await _send_error(
            ws, errors.PROVIDER_UNAVAILABLE, "Live transcription is not available on this server.", 1011
        )
        return

    detector = VoiceActivityDetector(vad_path, max_speech_seconds=15.0)
    model = start.get("model") if isinstance(start.get("model"), str) else None
    received_seconds = 0.0
    in_speech = False
    await ws.send_json({"type": "ready"})

    async def emit(spans) -> None:
        for span in spans:
            routed = await container.router.transcribe(
                AudioClip(samples=span.samples), TranscribeOptions(language="ja"), model=model
            )
            if routed.value.text:
                await ws.send_json(
                    {
                        "type": "segment",
                        "start": round(span.start, 3),
                        "end": round(span.end, 3),
                        "text": routed.value.text,
                        "model": routed.model_id,
                    }
                )

    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                data = message["bytes"]
                if len(data) > _MAX_FRAME_BYTES or len(data) % 2:
                    await _send_error(
                        ws, errors.VALIDATION_FAILED, "Frames must be PCM16 and at most 64 KiB.", 1009
                    )
                    return
                samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
                received_seconds += len(samples) / SAMPLE_RATE
                if received_seconds > settings.max_audio_seconds * 5:
                    await _send_error(ws, errors.AUDIO_TOO_LONG, "Stream length limit reached.", 1009)
                    return
                spans = list(detector.feed(samples))
                if detector.speech_in_progress and not in_speech:
                    await ws.send_json({"type": "speech_start"})
                in_speech = detector.speech_in_progress
                await emit(spans)
            elif message.get("text") is not None:
                try:
                    control = json.loads(message["text"])
                except ValueError:
                    control = {}
                if control.get("type") == "stop":
                    await emit(list(detector.finish()))
                    await ws.send_json({"type": "done"})
                    await ws.close()
                    return
    except WebSocketDisconnect:
        return
    except AppError as exc:
        await _send_error(ws, exc.code, exc.message, 1011)
    except Exception:
        log.exception("stream failed")
        await _send_error(ws, errors.INTERNAL_ERROR, "Internal error.", 1011)
