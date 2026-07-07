# services/notification/Dockerfile
# Multi-stage build

FROM python:3.12-slim AS builder
WORKDIR /app

COPY services/notification/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Imagem 
FROM python:3.12-slim AS runner

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY --from=builder /root/.local /home/app/.local

# Copia código
COPY --chown=app:app shared/ ./shared/
COPY --chown=app:app services/notification/ ./services/notification/

# Cria diretório para mock emails
RUN mkdir -p /tmp/notifications && chown -R app:app /tmp/notifications

USER app
ENV PATH=/home/app/.local/bin:$PATH
ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["uvicorn", "services.notification.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "2"]
