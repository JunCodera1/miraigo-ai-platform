"""HTTP contract tests through the real app, with a fake speech model and a fake backend."""

import pytest

from japanese_ai.providers.base import ProviderRejected
from tests.conftest import ADMIN_TOKEN, FakeASR, make_client, make_settings, wav_bytes

PRIMARY = "sensevoice-small-int8"


@pytest.fixture
def fake():
    return FakeASR(None, text="東京に行きました")


@pytest.fixture
def client(fake):
    test_client, container = make_client()
    fake.spec = container.registry.get(PRIMARY)
    container.pool._instances[PRIMARY] = fake
    with test_client as c:
        yield c


def assert_envelope(body, status):
    assert body["status"] == status
    assert {"message", "path", "timestamp", "requestId"} <= body.keys()


def test_liveness_needs_no_auth(client):
    response = client.get("/health/live")
    assert response.status_code == 200 and response.json()["data"] == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_request_id_is_echoed_when_well_formed(client):
    assert (
        client.get("/health/live", headers={"X-Request-Id": "abc12345-xyz"}).headers["x-request-id"]
        == "abc12345-xyz"
    )
    assert (
        client.get("/health/live", headers={"X-Request-Id": "bad id!"}).headers["x-request-id"] != "bad id!"
    )


def test_readiness_reports_capabilities(client):
    data = client.get("/health/ready").json()["data"]
    assert data["capabilities"] == {"language": True, "asr": True, "pronunciation": True}


def test_protected_endpoints_require_auth(client):
    response = client.post("/api/v1/language/analyze", json={"text": "猫"})
    assert response.status_code == 401
    body = response.json()
    assert_envelope(body, 401)
    assert body["errorCode"] == "AI_AUTH_REQUIRED"


def test_analyze(client, auth):
    response = client.post("/api/v1/language/analyze", json={"text": "私は猫が好きです。"}, headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert_envelope(body, 200)
    data = body["data"]
    assert data["reading"] == "わたしはねこがすきです。"
    assert data["romaji"] == "watashi wa neko ga suki desu"
    first = data["tokens"][0]
    assert first["furigana"] == [{"text": "私", "reading": "わたし"}]
    assert {"posDetail", "conjugationForm", "isOov"} <= first.keys()


def test_validation_errors_use_the_envelope(client, auth):
    response = client.post("/api/v1/language/analyze", json={"text": ""}, headers=auth)
    assert response.status_code == 422
    body = response.json()
    assert body["errorCode"] == "AI_VALIDATION_FAILED" and body["errors"][0]["field"] == "text"


def test_text_length_limit(auth):
    test_client, _ = make_client(make_settings(max_text_chars=5))
    with test_client as c:
        response = c.post("/api/v1/language/analyze", json={"text": "あいうえおか"}, headers=auth)
    assert response.status_code == 422


def test_unknown_route_uses_the_envelope(client):
    body = client.get("/api/v1/nope").json()
    assert body["errorCode"] == "AI_NOT_FOUND" and body["status"] == 404


def test_transcribe_json(client, auth, fake):
    response = client.post(
        "/api/v1/speech/transcribe", files={"file": ("a.wav", wav_bytes(2.0), "audio/wav")}, headers=auth
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["text"] == "東京に行きました"
    assert data["durationSeconds"] == pytest.approx(2.0, abs=0.01)
    assert data["meta"]["model"] == PRIMARY and data["meta"]["fallbackUsed"] is False
    assert fake.calls == 1


def test_transcribe_srt(client, auth):
    response = client.post(
        "/api/v1/speech/transcribe",
        files={"file": ("a.wav", wav_bytes(1.0), "audio/wav")},
        data={"responseFormat": "srt"},
        headers=auth,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-subrip")
    assert response.text.startswith("1\n00:00:00,000 --> 00:00:01,000\n東京に行きました")


def test_not_audio_is_rejected(client, auth):
    response = client.post(
        "/api/v1/speech/transcribe",
        files={"file": ("a.wav", b"this is not audio" * 100, "audio/wav")},
        headers=auth,
    )
    assert response.status_code == 400 and response.json()["errorCode"] == "AI_AUDIO_INVALID"


def test_empty_upload_is_rejected(client, auth):
    response = client.post(
        "/api/v1/speech/transcribe", files={"file": ("a.wav", b"", "audio/wav")}, headers=auth
    )
    assert response.json()["errorCode"] == "AI_AUDIO_EMPTY"


def test_upload_size_limit(auth):
    test_client, _ = make_client(make_settings(max_upload_mb=0))
    with test_client as c:
        response = c.post(
            "/api/v1/speech/transcribe", files={"file": ("a.wav", wav_bytes(1.0), "audio/wav")}, headers=auth
        )
    assert response.status_code == 413 and response.json()["errorCode"] == "AI_FILE_TOO_LARGE"


def test_audio_length_limit(client, auth):
    response = client.post(
        "/api/v1/pronunciation/evaluate",
        files={"file": ("a.wav", wav_bytes(31.0), "audio/wav")},
        data={"referenceText": "東京"},
        headers=auth,
    )
    assert response.status_code == 413 and response.json()["errorCode"] == "AI_AUDIO_TOO_LONG"


def test_unknown_model_is_404(client, auth):
    response = client.post(
        "/api/v1/speech/transcribe",
        files={"file": ("a.wav", wav_bytes(1.0), "audio/wav")},
        data={"model": "no-such-model"},
        headers=auth,
    )
    assert response.status_code == 404 and response.json()["errorCode"] == "AI_MODEL_NOT_FOUND"


def test_all_providers_failing_is_503(client, auth, fake):
    fake.fail = ProviderRejected("nope")
    response = client.post(
        "/api/v1/speech/transcribe", files={"file": ("a.wav", wav_bytes(1.0), "audio/wav")}, headers=auth
    )
    assert response.status_code == 503
    assert response.json()["errorCode"] == "AI_PROVIDER_UNAVAILABLE"


def test_pronunciation_perfect(client, auth):
    response = client.post(
        "/api/v1/pronunciation/evaluate",
        files={"file": ("a.wav", wav_bytes(2.0), "audio/wav")},
        data={"referenceText": "東京に行きました"},
        headers=auth,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["scores"] == {"overall": 100, "accuracy": 100, "completeness": 100}
    assert data["method"] == "asr_alignment_v0" and data["limitations"]
    assert data["speechRateMoraePerSecond"] > 0


def test_pronunciation_reports_issues(client, auth, fake):
    fake.text = "ときょうに行きました"
    data = client.post(
        "/api/v1/pronunciation/evaluate",
        files={"file": ("a.wav", wav_bytes(2.0), "audio/wav")},
        data={"referenceText": "東京に行きました"},
        headers=auth,
    ).json()["data"]
    tokyo = data["words"][0]
    assert tokyo["status"] == "partial"
    assert tokyo["issues"][0]["type"] == "long_vowel_shortened"
    assert data["scores"]["overall"] < 100


def test_pronunciation_silence_is_422(client, auth):
    response = client.post(
        "/api/v1/pronunciation/evaluate",
        files={"file": ("a.wav", wav_bytes(1.0, amplitude=0.0), "audio/wav")},
        data={"referenceText": "東京"},
        headers=auth,
    )
    assert response.status_code == 422 and response.json()["errorCode"] == "AI_AUDIO_EMPTY"


def test_pronunciation_needs_japanese_reference(client, auth):
    response = client.post(
        "/api/v1/pronunciation/evaluate",
        files={"file": ("a.wav", wav_bytes(1.0), "audio/wav")},
        data={"referenceText": "!!!"},
        headers=auth,
    )
    assert response.status_code == 422 and response.json()["errorCode"] == "AI_TEXT_NOT_JAPANESE"


def test_rate_limit(auth):
    test_client, _ = make_client(make_settings(rate_limit_per_minute=2))
    with test_client as c:
        statuses = [
            c.post("/api/v1/language/analyze", json={"text": "猫"}, headers=auth).status_code
            for _ in range(3)
        ]
        last = c.post("/api/v1/language/analyze", json={"text": "猫"}, headers=auth)
    assert statuses == [200, 200, 429]
    assert last.headers["retry-after"] and last.json()["errorCode"] == "AI_RATE_LIMITED"


def test_models_listing(client, auth):
    models = {m["id"]: m for m in client.get("/api/v1/models", headers=auth).json()["data"]}
    assert models[PRIMARY]["routingRole"] == "primary"
    assert models["legacy-voiceai"]["enabled"] is False


def test_usage_is_admin_only(client, auth):
    assert client.get("/api/v1/admin/usage", headers=auth).status_code == 403
    response = client.get("/api/v1/admin/usage", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert response.status_code == 200


def test_openapi_lists_the_contract(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/api/v1/speech/transcribe",
        "/api/v1/pronunciation/evaluate",
        "/api/v1/language/analyze",
    } <= paths.keys()


def test_cors_preflight(client):
    response = client.options(
        "/api/v1/language/analyze",
        headers={"Origin": "http://localhost:8081", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"


def test_pronunciation_uses_its_own_route(auth):
    test_client, container = make_client()
    asr_fake = FakeASR(container.registry.get(PRIMARY), text="東京")
    pron_fake = FakeASR(container.registry.get("reazonspeech-zipformer-ja"), text="東京")
    container.pool._instances[PRIMARY] = asr_fake
    container.pool._instances["reazonspeech-zipformer-ja"] = pron_fake
    with test_client as c:
        data = c.post(
            "/api/v1/pronunciation/evaluate",
            files={"file": ("a.wav", wav_bytes(1.0), "audio/wav")},
            data={"referenceText": "東京"},
            headers=auth,
        ).json()["data"]
        models = {m["id"]: m for m in c.get("/api/v1/models", headers=auth).json()["data"]}
    assert data["meta"]["model"] == "reazonspeech-zipformer-ja"
    assert (pron_fake.calls, asr_fake.calls) == (1, 0)
    assert models["reazonspeech-zipformer-ja"]["routingRoles"] == {
        "asr": "fallback",
        "pronunciation": "primary",
    }
