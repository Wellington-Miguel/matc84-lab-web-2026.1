FROM python:3.12-slim

WORKDIR /app

# Instala as dependências primeiro para aproveitar o cache do Docker
COPY services/payment/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código compartilhado e o microsserviço
COPY shared /app/shared
COPY services/payment /app/services/payment

ENV PYTHONPATH=/app

CMD ["uvicorn", "services.payment.main:app", "--host", "0.0.0.0", "--port", "8000"]