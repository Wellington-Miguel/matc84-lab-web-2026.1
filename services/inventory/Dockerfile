# services/inventory/Dockerfile
# Multi-stage build — imagem final enxuta e sem dependências de build

FROM python:3.12-slim AS builder
WORKDIR /app

# Instala dependências em camada separada (cache do Docker)
COPY services/inventory/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Imagem 
FROM python:3.12-slim AS runner

# Usuário não-root (segurança)
RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# Copia dependências instaladas
COPY --from=builder /root/.local /home/app/.local

# Copia código
COPY --chown=app:app shared/ ./shared/
COPY --chown=app:app services/inventory/ ./services/inventory/

USER app
ENV PATH=/home/app/.local/bin:$PATH
ENV PYTHONPATH=/app

EXPOSE 8001

CMD ["uvicorn", "services.inventory.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
