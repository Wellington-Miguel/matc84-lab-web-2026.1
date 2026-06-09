# Distribuidora de Bebidas — Sistema Distribuído de Alta Escala

## Arquitetura
- **180k vendas/dia** | **1000 req/s** | **latência p99 < 500ms** | **disponibilidade ≥ 90%**
- AWS (us-east-1) | Python | Terraform | Aurora PostgreSQL | ElastiCache Redis | SQS

## Estrutura
```
bebidas-distribuidor/
├── infra/                        # Infraestrutura como código (Terraform)
│   ├── modules/
│   │   ├── vpc/                  # Rede: subnets públicas/privadas, NAT
│   │   ├── alb/                  # Application Load Balancer
│   │   ├── asg/                  # Auto Scaling Group (EC2 stateless)
│   │   ├── rds/                  # Aurora PostgreSQL Multi-AZ
│   │   ├── elasticache/          # Redis (sessão + Data Grid SBA)
│   │   ├── sqs/                  # Filas de mensageria (+ DLQ)
│   │   └── lambda/               # Data Writers (consumidores SQS)
│   └── environments/
│       └── dev/                  # Configuração do ambiente de dev
│
├── services/                     # Microsserviços Python (FastAPI)
│   ├── identity/                 # Autenticação JWT stateless
│   ├── order/                    # Pedidos + idempotência
│   ├── inventory/                # Estoque + OCC Redis
│   ├── catalog/                  # Catálogo de produtos
│   ├── payment/                  # Pagamentos
│   └── notification/             # Alertas (email/SMS)
│
├── shared/                       # Código compartilhado entre serviços
│   ├── retry.py                  # Exponential Backoff + Jitter
│   ├── idempotency.py            # Protocolo Check-then-Act
│   └── logger.py                 # Logs estruturados JSON
│
└── .github/workflows/            # CI/CD (GitHub Actions)
    └── deploy.yml
```

## Como rodar localmente
```bash
# 1. Configure AWS CLI
aws configure

# 2. Suba a infraestrutura
cd infra/environments/dev
terraform init && terraform apply

# 3. Rode um serviço
cd services/order
pip install -r requirements.txt
uvicorn main:app --reload
```
