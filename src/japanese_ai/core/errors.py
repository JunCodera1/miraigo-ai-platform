"""Application errors. Every failure a client can see is an ``AppError`` with a stable code."""

from __future__ import annotations

from typing import Any

from starlette.exceptions import HTTPException


class AppError(HTTPException):
    """An error with an HTTP status and a stable machine-readable code.

    It subclasses ``HTTPException`` on purpose: FastAPI re-raises HTTP exceptions thrown while
    it parses a request body, but turns any other exception into a generic 400.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 400,
        *,
        errors: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status, detail=message, headers=headers)
        self.code = code
        self.message = message
        self.errors = errors


# Codes are part of the public contract (docs/ERRORS.md). Do not rename them.
AUTH_REQUIRED = "AI_AUTH_REQUIRED"
AUTH_INVALID = "AI_AUTH_INVALID"
AUTH_UNAVAILABLE = "AI_AUTH_UNAVAILABLE"
FORBIDDEN = "AI_FORBIDDEN"
VALIDATION_FAILED = "AI_VALIDATION_FAILED"
BAD_REQUEST = "AI_BAD_REQUEST"
NOT_FOUND = "AI_NOT_FOUND"
METHOD_NOT_ALLOWED = "AI_METHOD_NOT_ALLOWED"
FILE_TOO_LARGE = "AI_FILE_TOO_LARGE"
AUDIO_INVALID = "AI_AUDIO_INVALID"
AUDIO_TOO_LONG = "AI_AUDIO_TOO_LONG"
AUDIO_EMPTY = "AI_AUDIO_EMPTY"
TEXT_NOT_JAPANESE = "AI_TEXT_NOT_JAPANESE"
RATE_LIMITED = "AI_RATE_LIMITED"
BUSY = "AI_BUSY"
MODEL_NOT_FOUND = "AI_MODEL_NOT_FOUND"
PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
PROVIDER_TIMEOUT = "AI_PROVIDER_TIMEOUT"
INTERNAL_ERROR = "AI_INTERNAL_ERROR"

_STATUS_CODES = {
    400: BAD_REQUEST,
    401: AUTH_REQUIRED,
    403: FORBIDDEN,
    404: NOT_FOUND,
    405: METHOD_NOT_ALLOWED,
    413: FILE_TOO_LARGE,
    429: RATE_LIMITED,
}


def code_for_status(status: int) -> str:
    """Code for errors raised by the framework itself (unknown route, wrong method, ...)."""
    return _STATUS_CODES.get(status, INTERNAL_ERROR if status >= 500 else BAD_REQUEST)
