"""Entrypoint: ``japanese-ai`` (or ``python -m japanese_ai.main``)."""

from __future__ import annotations

import uvicorn

from japanese_ai.core.config import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "japanese_ai.gateway.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_config=None,
        proxy_headers=True,
    )


if __name__ == "__main__":
    run()
