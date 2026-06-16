from fastapi import FastAPI

app = FastAPI(
    title="Distribuidora de Bebidas API",
    description="Sistema Distribuído de Alta Disponibilidade (Monólito Modular)",
    version="1.0.0"
)

@app.get("/health", tags=["Observabilidade"])
def health_check():
    """
    Endpoint de checagem de saúde para métricas de disponibilidade.
    """
    return {"status": "ok", "mensagem": "Sistema operando normalmente."}