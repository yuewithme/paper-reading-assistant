FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_CONCURRENT_DOWNLOADS=4 \
    UV_LINK_MODE=copy \
    UV_DEFAULT_INDEX="https://mirrors.cloud.tencent.com/pypi/simple" \
    PIP_INDEX_URL="https://mirrors.cloud.tencent.com/pypi/simple" \
    PATH="/app/backend/.venv/bin:${PATH}"

RUN sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::http::Timeout=30 update \
    && apt-get install --yes --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir uv==0.11.19

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock /app/backend/

RUN uv export \
        --project /app/backend \
        --frozen \
        --no-dev \
        --no-emit-project \
        --format requirements.txt \
        --output-file /tmp/requirements.txt \
    && uv pip install --system --require-hashes --requirements /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY backend/app /app/backend/app
RUN uv pip install --system --no-deps /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=*"]
