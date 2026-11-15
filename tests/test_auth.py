import asyncio

import httpx
import pytest

from japanese_ai.core.errors import AppError
from japanese_ai.infrastructure.auth import BackendAuthenticator
from tests.conftest import VALID_TOKEN, backend_transport, make_settings


def run(coro):
    return asyncio.run(coro)


def test_valid_token_becomes_a_user_principal():
    auth = BackendAuthenticator(make_settings(), transport=backend_transport())
    principal = run(auth.authenticate(f"Bearer {VALID_TOKEN}", None))
    assert (principal.kind, principal.id, principal.username, principal.role) == (
        "user",
        "7",
        "learner",
        "USER",
    )


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer x"])
def test_missing_or_malformed_header_is_401(header):
    auth = BackendAuthenticator(make_settings(), transport=backend_transport())
    with pytest.raises(AppError) as info:
        run(auth.authenticate(header, None))
    assert info.value.status_code == 401 and info.value.code == "AI_AUTH_REQUIRED"


def test_rejected_token_is_401():
    auth = BackendAuthenticator(make_settings(), transport=backend_transport())
    with pytest.raises(AppError) as info:
        run(auth.authenticate("Bearer revoked-or-refresh-token", None))
    assert info.value.code == "AI_AUTH_INVALID"


def test_backend_down_fails_closed_with_503():
    def boom(request):
        raise httpx.ConnectError("refused")

    auth = BackendAuthenticator(make_settings(), transport=httpx.MockTransport(boom))
    with pytest.raises(AppError) as info:
        run(auth.authenticate(f"Bearer {VALID_TOKEN}", None))
    assert info.value.status_code == 503


def test_successful_checks_are_cached():
    calls = []
    inner = backend_transport()

    def counting(request):
        calls.append(1)
        return inner.handle_request(request)

    auth = BackendAuthenticator(make_settings(), transport=httpx.MockTransport(counting))
    run(auth.authenticate(f"Bearer {VALID_TOKEN}", None))
    run(auth.authenticate(f"Bearer {VALID_TOKEN}", None))
    assert len(calls) == 1


def test_cache_can_be_disabled():
    calls = []
    inner = backend_transport()

    def counting(request):
        calls.append(1)
        return inner.handle_request(request)

    auth = BackendAuthenticator(
        make_settings(auth_cache_ttl_seconds=0), transport=httpx.MockTransport(counting)
    )
    run(auth.authenticate(f"Bearer {VALID_TOKEN}", None))
    run(auth.authenticate(f"Bearer {VALID_TOKEN}", None))
    assert len(calls) == 2


def test_service_api_key():
    auth = BackendAuthenticator(make_settings(), transport=backend_transport())
    assert run(auth.authenticate(None, "service-key-abc")).kind == "service"
    with pytest.raises(AppError):
        run(auth.authenticate(None, "wrong"))


def test_auth_none_is_refused_in_production():
    with pytest.raises(ValueError, match="not allowed"):
        make_settings(env="production", auth_mode="none")


def test_home_is_expanded_in_paths():
    from pathlib import Path

    settings = make_settings(models_dir="~/some-models")
    assert settings.models_dir == Path.home() / "some-models"
