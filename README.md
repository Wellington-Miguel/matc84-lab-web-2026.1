# Projeto Prático - Plataforma de E-commerce Distribuída

> ⚠️ **Unificamos o projeto nessa branch mas os originais estão em:**
>
> - https://github.com/palmsb/labWebCompra
> - https://github.com/palmsb/labWebSugestao
> - https://github.com/palmsb/labWebFront

## Sobre o Projeto

Este projeto consiste em uma plataforma de e-commerce baseada em microsserviços, desenvolvida para aplicar conceitos de arquitetura distribuída, computação em nuvem, escalabilidade, resiliência e observabilidade.

A solução foi projetada utilizando **AWS**, **Render** e **Cloudflare**, separando serviços críticos e não críticos para garantir maior disponibilidade, flexibilidade e tolerância a falhas.

## Arquitetura

O sistema é composto por três aplicações principais:

### Frontend
Interface responsável pela experiência do usuário e consumo das APIs.

### API de Compras
Serviço responsável pelo processamento de pedidos e operações transacionais.

### API de Sugestões
Serviço responsável pela recomendação de produtos e funcionalidades auxiliares.

## Tecnologias Utilizadas

### Frontend
- React
- TypeScript
- Vite

### Backend
- Node.js
- Express
- TypeScript
- PostgreSQL
- Docker

### Infraestrutura
- AWS
- Render
- Cloudflare

## Estrutura do Projeto

```
.
├── labwebCompras/
├── labwebFront/
├── labwebSugestao/
└── docs/
```

## Objetivos do Projeto

- Aplicar conceitos de microsserviços
- Implementar estratégias de resiliência e tolerância a falhas
- Explorar soluções em nuvem utilizando serviços gratuitos
- Desenvolver uma arquitetura escalável e observável
- Aplicar princípios de Engenharia do Caos
- Avaliar padrões modernos de integração e mensageria

## Equipe

- Ana Beatriz Brito
- Igor Falcão
- Igor Marinho Argollo
- João Xavier
- Leonardo Alakija
- Rafael Rocha
- Paloma Brito
- Pedro Elias
- Thiago Coutinho