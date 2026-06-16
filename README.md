# Sistema Distribuído - Distribuidora de Bebidas 

Este é o repositório da **Equipe 04 - Engenharia do Caos** para a disciplina de Laboratório de Programação Web. 

O sistema foi arquitetado como um **Monólito Modular** focado em alta disponibilidade, idempotência e observabilidade, utilizando o padrão *Transactional Outbox*.

## Objetivos do Projeto

O objetivo principal deste projeto é o planejamento e desenvolvimento do sistema core de uma distribuidora de bebidas de larga escala, projetado para absorver com alta resiliência um volume transacional de 180.000 vendas por dia e picos de 20 a 30 requisições por segundo. O projeto é guiado por três diretrizes fundamentais:
* **Custo Zero de Infraestrutura:** Operação planejada para rodar estritamente dentro dos limites gratuitos do AWS Free Tier.
* **Resiliência e Confiabilidade:** Garantia de consistência através da aplicação prática de padrões de sistemas distribuídos, como idempotência, políticas de retries estruturadas e filas duráveis.
* **Observabilidade e Confiabilidade Baseada em Evidências:** Adoção de métricas, logs e definição clara de Objetivos de Nível de Serviço (SLOs) e Indicadores de Nível de Serviço (SLIs) como a espinha dorsal para o monitoramento contínuo da saúde do ecossistema.

## Tecnologias Utilizadas

Para atender aos critérios de desempenho e restrição orçamentária, a stack tecnológica escolhida compreende:
* **FastAPI:** Framework moderno e de alto desempenho para a construção da API e ingestão de pedidos.
* **PostgreSQL:** Banco de dados relacional responsável pela persistência e pela fila interna de mensageria assíncrona.
* **Docker:** Utilizado para a conteinização e isolamento dos serviços da aplicação e do banco de dados.
* **Nginx & Let's Encrypt:** Configuração de proxy reverso e terminação TLS para assegurar a criptografia em trânsito.
* **Terraform:** Ferramenta de Infraestrutura como Código (IaC) para provisionamento automatizado de toda a infraestrutura na nuvem.
* **OpenTelemetry, Prometheus & Grafana:** Ferramentas essenciais para a coleta, armazenamento e visualização tridimensional da telemetria do sistema.

## Estrutura do Projeto

A aplicação adota a arquitetura de um **Monólito Modular**, organizando os componentes de forma desacoplada para isolar as responsabilidades do sistema:

```text
distribuidora-backend/
├── app/
│   ├── main.py              # Ponto de entrada da aplicação FastAPI e inicialização
│   ├── api/                 # Camada de Ingestão: Definição de endpoints e validação de chaves de idempotência
│   ├── core/                # Configurações globais de segurança, criptografia e ambiente
│   ├── models/              # Modelos relacionais (SQLAlchemy) para pedidos, estoque e tabela outbox
│   ├── schemas/             # Esquemas de validação de dados de entrada e saída (Pydantic)
│   └── services/            # Camada de regras de negócio e execução assíncrona do Transactional Outbox Worker
├── docker-compose.yml       # Orquestração local do contêiner do banco de dados PostgreSQL
├── README.md                # Documentação técnica e guia de onboarding do projeto
└── .gitignore               # Restrição de arquivos temporários e ambientes virtuais
```

## Equipe

* Juan Reis dos Santos
* Dely Oliveira
* Isaac Borges
* Maurício Matchal
* Caio Mello
* Vinícius Coutinho
* Jean Loui Bernard
* Júlio César

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

