"""Caller authentication.

MiraiGo access tokens are checked by asking the MiraiGo backend who the caller is
(``GET /api/v1/users/me``), because a token is only valid there if its signature is right, it is
an *access* token, and it has not been revoked in Redis. Re-implementing those three checks here
would mean sharing the JWT secret and the backend's Redis layout (lab decision D-009).

Trusted servers can instead send ``X-API-Key``.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

import httpx

from japanese_ai.core import errors
from japanese_ai.core.config import Settings
from japanese_ai.core.errors import AppError
from japanese_ai.core.logging import get_logger

log = get_logger("auth")
_CACHE_MAX = 10_000


@dataclass(frozen=True)
class Principal:
    kind: str  # "user" | "service" | "anonymous"
    id: str
    username: str | None = None
    role: str | None = None

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.id}"


ANONYMOUS = Principal(kind="anonymous", id="dev")


class BackendAuthenticator:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.backend_base_url.rstrip("/"),
            timeout=settings.auth_timeout_seconds,
            transport=transport,
        )
        self._cache: dict[str, tuple[float, Principal]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def authenticate(self, authorization: str | None, api_key: str | None) -> Principal:
        if api_key:
            for index, key in enumerate(self._settings.service_keys):
                if hmac.compare_digest(api_key.encode(), key.encode()):
                    return Principal(kind="service", id=f"key{index + 1}")
            raise AppError(errors.AUTH_INVALID, "Invalid API key.", 401)

        if self._settings.auth_mode == "none":
            return ANONYMOUS

        if not authorization or not authorization.startswith("Bearer ") or len(authorization) < 16:
            raise AppError(
                errors.AUTH_REQUIRED, "Sign in required.", 401, headers={"WWW-Authenticate": "Bearer"}
            )
        token = authorization[7:].strip()
        return await self.verify_token(token)

    async def verify_token(self, token: str) -> Principal:
        cache_key = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

        try:
            response = await self._client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
            )
        except httpx.HTTPError as exc:
            log.error("auth backend unreachable", extra={"error": type(exc).__name__})
            raise AppError(errors.AUTH_UNAVAILABLE, "Sign-in could not be checked right now.", 503) from None

        if response.status_code in (401, 403):
            raise AppError(
                errors.AUTH_INVALID,
                "Your session is invalid or has expired.",
                401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        if response.status_code != 200:
            log.error("auth backend error", extra={"status": response.status_code})
            raise AppError(errors.AUTH_UNAVAILABLE, "Sign-in could not be checked right now.", 503)
        try:
            data = response.json()["data"]
            principal = Principal(
                kind="user", id=str(data["id"]), username=data.get("username"), role=data.get("role")
            )
        except (ValueError, KeyError, TypeError):
            raise AppError(errors.AUTH_UNAVAILABLE, "Sign-in could not be checked right now.", 503) from None

        if self._settings.auth_cache_ttl_seconds > 0:
            if len(self._cache) >= _CACHE_MAX:
                self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
                if len(self._cache) >= _CACHE_MAX:
                    self._cache.clear()
            self._cache[cache_key] = (now + self._settings.auth_cache_ttl_seconds, principal)
        return principal
