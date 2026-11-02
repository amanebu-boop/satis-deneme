FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-calc libreoffice-writer fonts-dejavu-core fonts-liberation \
    postgresql-client openssl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY AGENTS.md ./AGENTS.md
COPY agents ./agents
COPY docs/knowledge ./docs/knowledge
COPY scripts ./scripts
COPY web ./web
COPY templates ./templates
COPY Ersen_Makina_Teklif_Sablonu_duzenlenmis.xlsx ./

RUN pip install --upgrade pip && pip install . \
    && chmod +x /app/scripts/backup.sh /app/scripts/restore.sh

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data/documents \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
