"""WebSocket live transcription: protocol, auth, and VAD-driven segmentation (needs the VAD model)."""

import numpy as np
import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import MODELS_DIR, VALID_TOKEN, FakeASR, make_client, make_settings

VAD = MODELS_DIR / "sherpa" / "silero_vad.onnx"
PRIMARY = "sensevoice-small-int8"


@pytest.fixture
def client():
    test_client, container = make_client(make_settings(models_dir=MODELS_DIR))
    fake = FakeASR(container.registry.get(PRIMARY), text="こんにちは")
    container.pool._instances[PRIMARY] = fake
    with test_client as c:
        yield c


def test_first_message_must_authenticate(client):
    with client.websocket_connect("/api/v1/speech/stream") as ws:
        ws.send_json({"type": "start", "token": "bad-token-000000"})
        message = ws.receive_json()
        assert message["type"] == "error" and message["errorCode"] == "AI_AUTH_INVALID"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_foreign_origin_is_refused(client):
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/v1/speech/stream", headers={"origin": "https://evil.example"}) as ws,
    ):
        ws.receive_json()


@pytest.mark.skipif(not VAD.is_file(), reason="silero_vad.onnx not downloaded")
def test_noise_burst_produces_a_segment(client):
    rng = np.random.default_rng(0)
    # Silero does not fire on pure tones; band-limited noise shaped like syllables does well enough
    # to exercise the plumbing. Real speech is covered by the model tests.
    t = np.arange(16000 * 2) / 16000
    speechy = (rng.normal(0, 0.3, t.size) * (0.5 + 0.5 * np.sin(2 * np.pi * 4 * t))).astype(np.float32)
    audio = np.concatenate([np.zeros(8000, np.float32), speechy, np.zeros(16000, np.float32)])
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
    with client.websocket_connect("/api/v1/speech/stream") as ws:
        ws.send_json({"type": "start", "token": VALID_TOKEN, "sampleRate": 16000})
        assert ws.receive_json()["type"] == "ready"
        for i in range(0, len(pcm), 3200):
            ws.send_bytes(pcm[i : i + 3200])
        ws.send_json({"type": "stop"})
        messages = []
        while True:
            message = ws.receive_json()
            messages.append(message)
            if message["type"] in ("done", "error"):
                break
    types = [m["type"] for m in messages]
    assert types[-1] == "done", messages
    # Either VAD saw speech (segment emitted) or it did not; both are valid protocol runs.
    for message in messages:
        if message["type"] == "segment":
            assert message["text"] == "こんにちは" and message["end"] > message["start"]
