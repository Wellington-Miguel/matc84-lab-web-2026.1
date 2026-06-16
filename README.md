# Sistema Distribuído - Distribuidora de Bebidas 

Este é o repositório da **Equipe 04 - Engenharia do Caos** para a disciplina de Laboratório de Programação Web. 

O sistema foi arquitetado como um **Monólito Modular** focado em alta disponibilidade, idempotência e observabilidade, utilizando o padrão *Transactional Outbox*.

## Stack Tecnológica
* **API:** FastAPI + Uvicorn
* **Banco de Dados e Fila:** PostgreSQL (Docker)
* **Gerenciador de Dependências:** UV (ou Poetry)

## Como rodar localmente (Setup)

1. **Suba o Banco de Dados:**
   ```bash
   docker-compose up -d
2. **Instale as dependências e ative o ambiente virtual:**
    ```bash
   uv sync
   source .venv/bin/activate  # No Windows: .venv\Scripts\activate
3. **Inicie o servidor local:**
    ```bash
    uvicorn app.main:app --reload
4. **Acesse a documentação gerada automaticamente no navegador:**
http://localhost:8000/docs

