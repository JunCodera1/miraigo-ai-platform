# Plain Dockerfile syntax only (no BuildKit features): it must build with the classic builder.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    JAI_HOST=0.0.0.0 \
    JAI_PORT=8090 \
    JAI_MODELS_DIR=/models \
    HF_HOME=/models/hf

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[local]"

RUN useradd --system --uid 10001 --home /app jai \
    && mkdir -p /models \
    && chown jai /models
USER jai
# With a read-only root filesystem, mount a tmpfs on /tmp (mode 1777): uploads are staged there
# and Starlette spools large multipart bodies there too.

EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/health/live', timeout=4).status == 200 else 1)"

CMD ["japanese-ai"]
