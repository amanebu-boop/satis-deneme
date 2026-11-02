FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-calc fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY templates ./templates
COPY web ./web

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && groupadd --system --gid 10001 salesapp \
    && useradd --system --uid 10001 --gid salesapp --home-dir /app --shell /usr/sbin/nologin salesapp \
    && mkdir -p /app/data/documents \
    && chown -R salesapp:salesapp /app

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
