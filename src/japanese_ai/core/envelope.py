"""Response envelope.

It mirrors the MiraiGo backend's ``ApiResponse`` (``status``, ``message``, ``errorCode``, ``data``,
``errors``, ``path``, ``timestamp``) so existing clients can unwrap both services with one code
path, and adds ``requestId`` for support and tracing. Field names are camelCase, like the backend.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, model_serializer
from pydantic.alias_generators import to_camel
from starlette.requests import Request
from starlette.responses import JSONResponse

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base for every public schema: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ApiResponse(CamelModel, Generic[T]):
    status: int
    message: str
    error_code: str | None = None
    data: T | None = None
    errors: Any | None = None
    path: str
    timestamp: str
    request_id: str | None = None

    @model_serializer(mode="wrap")
    def _omit_empty_envelope_fields(self, handler: Any) -> dict[str, Any]:
        # Like the backend (@JsonInclude NON_NULL), but only for the envelope itself: nullable
        # fields inside ``data`` stay present so clients can rely on them.
        data = handler(self)
        for key in ("errorCode", "error_code", "errors", "requestId", "request_id"):
            if data.get(key) is None:
                data.pop(key, None)
        return data


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def request_id_of(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def success(request: Request, data: T, message: str = "Success", status: int = 200) -> ApiResponse[T]:
    return ApiResponse[T](
        status=status,
        message=message,
        data=data,
        path=request.url.path,
        timestamp=_now(),
        request_id=request_id_of(request),
    )


def error_payload(
    *, status: int, code: str, message: str, path: str, request_id: str | None, errors: Any = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "message": message,
        "errorCode": code,
        "path": path,
        "timestamp": _now(),
    }
    if errors is not None:
        payload["errors"] = errors
    if request_id is not None:
        payload["requestId"] = request_id
    return payload


def error_response(
    request: Request,
    *,
    status: int,
    code: str,
    message: str,
    errors: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = error_payload(
        status=status,
        code=code,
        message=message,
        path=request.url.path,
        request_id=request_id_of(request),
        errors=errors,
    )
    return JSONResponse(payload, status_code=status, headers=headers)
