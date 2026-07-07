# services/catalog/Dockerfile
# Multi-stage build

FROM python:3.12-slim AS builder
WORKDIR /app

COPY services/catalog/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Imagem final ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY --from=builder /root/.local /home/app/.local

# Copia código
COPY --chown=app:app shared/ ./shared/
COPY --chown=app:app services/catalog/ ./services/catalog/

USER app
ENV PATH=/home/app/.local/bin:$PATH
ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["uvicorn", "services.catalog.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2"]
