"""Runtime configuration. Every value comes from the environment (prefix ``JAI_``) or a local ``.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "japanese-ai-platform"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JAI_", env_file=".env", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = 8090
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    docs_enabled: bool = True

    # --- Authentication -------------------------------------------------------------------
    # "backend": validate the caller's MiraiGo access token by asking the backend who it is.
    # "none": no authentication. Refused in production.
    auth_mode: Literal["backend", "none"] = "backend"
    backend_base_url: str = "http://localhost:8080"
    auth_timeout_seconds: float = 5.0
    # How long a successful token check is reused. A logged-out token stays usable here for
    # at most this long; 0 disables the cache.
    auth_cache_ttl_seconds: float = 60.0
    # Comma-separated keys for trusted servers (sent as ``X-API-Key``). Empty disables it.
    service_api_keys: str = ""

    cors_allowed_origins: str = "http://localhost:8081,http://localhost:3000"

    # --- Limits ---------------------------------------------------------------------------
    max_upload_mb: int = 25
    max_audio_seconds: float = 120.0
    max_pronunciation_audio_seconds: float = 30.0
    max_text_chars: int = 2000
    rate_limit_per_minute: int = 120
    inference_rate_limit_per_minute: int = 20
    max_concurrent_inference: int = 1
    inference_queue_timeout_seconds: float = 15.0

    # --- Models ---------------------------------------------------------------------------
    # Registry file; the packaged default is used when unset.
    models_file: Path | None = None
    models_dir: Path = Field(default=DEFAULT_DATA_DIR / "models")
    # Overrides ``routing.asr.primary`` from the registry.
    asr_model: str | None = None
    # Overrides ``routing.pronunciation.primary``.
    pronunciation_model: str | None = None
    # Load the primary speech model at startup instead of on the first request.
    warmup: bool = False

    # --- Media tools ----------------------------------------------------------------------
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    # Where uploads are staged. Defaults to the system temp dir; point it at real disk if
    # /tmp is RAM-backed.
    temp_dir: Path | None = None

    @field_validator("models_dir", "models_file", "temp_dir", mode="after")
    @classmethod
    def _expand_home(cls, value: Path | None) -> Path | None:
        # ``~`` in .env files is not expanded by the shell.
        return value.expanduser() if value is not None else None

    @model_validator(mode="after")
    def _refuse_open_production(self) -> Settings:
        if self.env == "production" and self.auth_mode == "none":
            raise ValueError("JAI_AUTH_MODE=none is not allowed when JAI_ENV=production")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return _split_csv(self.cors_allowed_origins)

    @property
    def service_keys(self) -> list[str]:
        return _split_csv(self.service_api_keys)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
