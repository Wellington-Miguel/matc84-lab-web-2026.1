import os
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, HTTPException, status, Query
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel, field_validator

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from shared.logger import get_logger, LogContext, Timer

logger = get_logger("catalog-service")

# Métricas
REQUISICOES_TOTAL = Counter(
    "http_requests_total", "Total de requisições HTTP", ["metodo", "caminho", "status"]
)
DURACAO_REQUISICOES = Histogram(
    "http_request_duration_seconds", "Duração das requisições", ["metodo", "caminho"]
)
PRODUTOS_TOTAL = Gauge("catalog_products_total", "Total de produtos ativos")
CACHE_ACERTOS = Counter("cache_hits_total", "Acertos de cache", ["tipo_recurso"])
CACHE_ERROS = Counter("cache_misses_total", "Erros de cache", ["tipo_recurso"])
PRODUTOS_CRIADOS = Counter("products_created_total", "Produtos criados")
PRODUTOS_ATUALIZADOS = Counter("products_updated_total", "Produtos atualizados")
PRODUTOS_DELETADOS = Counter("products_deleted_total", "Produtos deletados")

# Configuração
URL_BD = os.getenv("DATABASE_URL", "postgresql://bebidasadmin:[REDACTED]@localhost/bebidas")
URL_REDIS = os.getenv("REDIS_URL", "redis://localhost:6379")
TTL_CACHE = 3600

# Globais
pool_bd: asyncpg.Pool = None
cliente_redis: aioredis.Redis = None


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    global pool_bd, cliente_redis
    logger.info("catalog-service.iniciando")
    
    pool_bd = await asyncpg.create_pool(URL_BD, min_size=5, max_size=20)
    cliente_redis = aioredis.from_url(URL_REDIS, decode_responses=True)
    
    produtos_ativos = await pool_bd.fetchval("SELECT COUNT(*) FROM products WHERE active = true")
    PRODUTOS_TOTAL.set(produtos_ativos or 0)
    
    logger.info("catalog-service.pronto")
    yield
    
    await pool_bd.close()
    await cliente_redis.close()
    logger.info("catalog-service.encerrando")


app = FastAPI(title="Catalog Service", lifespan=ciclo_vida)


@app.middleware("http")
async def middleware_correlacao(requisicao: Request, proximo):
    id_correlacao = requisicao.headers.get("x-correlation-id") or str(uuid.uuid4())
    id_requisicao = str(uuid.uuid4())
    cronometro = Timer()
    codigo_status = 500

    with LogContext(correlation_id=id_correlacao, request_id=id_requisicao):
        try:
            resposta = await proximo(requisicao)
            codigo_status = resposta.status_code
            resposta.headers["x-correlation-id"] = id_correlacao
            return resposta
        finally:
            caminho = _obter_template_rota(requisicao)
            if caminho != "/metrics":
                REQUISICOES_TOTAL.labels(metodo=requisicao.method, caminho=caminho, status=str(codigo_status)).inc()
                DURACAO_REQUISICOES.labels(metodo=requisicao.method, caminho=caminho).observe(cronometro.elapsed_ms / 1000)


# Modelos
class RespostaCategoria(BaseModel):
    id: str
    nome: str
    descricao: Optional[str] = None
    data_criacao: str


class RespostaProduto(BaseModel):
    id: str
    sku: str
    nome: str
    descricao: Optional[str] = None
    preco: float
    id_categoria: Optional[str] = None
    nome_categoria: Optional[str] = None
    ativo: bool
    data_criacao: str
    data_atualizacao: str


class CriarProdutoRequisicao(BaseModel):
    sku: str
    nome: str
    descricao: Optional[str] = None
    preco: float
    id_categoria: Optional[str] = None

    @field_validator("sku")
    @classmethod
    def validar_sku(cls, v):
        if not v or len(v) < 3:
            raise ValueError("SKU deve ter no mínimo 3 caracteres")
        return v.upper()

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v):
        if not v or len(v) < 3:
            raise ValueError("Nome deve ter no mínimo 3 caracteres")
        return v

    @field_validator("preco")
    @classmethod
    def validar_preco(cls, v):
        if v <= 0:
            raise ValueError("Preço deve ser positivo")
        return round(v, 2)


class AtualizarProdutoRequisicao(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    preco: Optional[float] = None
    id_categoria: Optional[str] = None
    ativo: Optional[bool] = None

    @field_validator("preco")
    @classmethod
    def validar_preco(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Preço deve ser positivo")
        return round(v, 2) if v else None


class CriarCategoriaRequisicao(BaseModel):
    nome: str
    descricao: Optional[str] = None

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v):
        if not v or len(v) < 2:
            raise ValueError("Nome deve ter no mínimo 2 caracteres")
        return v


# Endpoints
@app.get("/health")
async def verificacao_saude():
    verificacoes = {}
    try:
        await pool_bd.fetchval("SELECT 1")
        verificacoes["bd"] = "ok"
    except Exception as e:
        verificacoes["bd"] = f"erro: {str(e)}"

    try:
        await cliente_redis.ping()
        verificacoes["redis"] = "ok"
    except Exception as e:
        verificacoes["redis"] = f"erro: {str(e)}"

    tudo_ok = all(v == "ok" for v in verificacoes.values())
    return JSONResponse(
        status_code=200 if tudo_ok else 503,
        content={"status": "saudavel" if tudo_ok else "degradado", "verificacoes": verificacoes}
    )


@app.get("/metrics")
async def metricas():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/catalogo/produtos", response_model=List[RespostaProduto])
async def listar_produtos(
    id_categoria: Optional[str] = Query(None),
    preco_minimo: Optional[float] = Query(None),
    preco_maximo: Optional[float] = Query(None),
    deslocamento: int = Query(0, ge=0),
    limite: int = Query(20, ge=1, le=100),
):
    cronometro = Timer()
    clausulas_where = ["p.active = true"]
    parametros = []
    numero_parametro = 1

    if id_categoria:
        clausulas_where.append(f"p.category_id = ${numero_parametro}")
        parametros.append(id_categoria)
        numero_parametro += 1

    if preco_minimo is not None:
        clausulas_where.append(f"p.price >= ${numero_parametro}")
        parametros.append(preco_minimo)
        numero_parametro += 1

    if preco_maximo is not None:
        clausulas_where.append(f"p.price <= ${numero_parametro}")
        parametros.append(preco_maximo)
        numero_parametro += 1

    sql_where = " AND ".join(clausulas_where)
    consulta = f"""
        SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
               c.name as category_name, p.active, p.created_at, p.updated_at
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE {sql_where}
        ORDER BY p.created_at DESC
        OFFSET ${numero_parametro} LIMIT ${numero_parametro + 1}
    """
    
    parametros.extend([deslocamento, limite])
    linhas = await pool_bd.fetch(consulta, *parametros)
    
    logger.info("catalogo.listar_produtos", extra={"quantidade": len(linhas), "tempo_ms": cronometro.elapsed_ms})
    
    return [_converter_linha_produto(linha) for linha in linhas]


@app.get("/catalogo/produtos/{id_produto}", response_model=RespostaProduto)
async def obter_produto(id_produto: str):
    cronometro = Timer()
    chave_cache = f"produto:{id_produto}"
    
    em_cache = await cliente_redis.get(chave_cache)
    if em_cache:
        CACHE_ACERTOS.labels(tipo_recurso="produto").inc()
        return json.loads(em_cache)

    CACHE_ERROS.labels(tipo_recurso="produto").inc()
    
    linha = await pool_bd.fetchrow(
        """SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
                  c.name as category_name, p.active, p.created_at, p.updated_at
           FROM products p
           LEFT JOIN categories c ON p.category_id = c.id
           WHERE p.id = $1 AND p.active = true""",
        id_produto,
    )

    if not linha:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    produto = _converter_linha_produto(linha)
    await cliente_redis.setex(chave_cache, TTL_CACHE, produto.model_dump_json())
    
    logger.info("catalogo.obter_produto", extra={"id_produto": id_produto, "tempo_ms": cronometro.elapsed_ms})
    return produto


@app.post("/catalogo/produtos", response_model=RespostaProduto, status_code=201)
async def criar_produto(requisicao: CriarProdutoRequisicao):
    cronometro = Timer()
    id_produto = str(uuid.uuid4())

    existente = await pool_bd.fetchval("SELECT id FROM products WHERE sku = $1", requisicao.sku)
    if existente:
        raise HTTPException(status_code=409, detail=f"SKU {requisicao.sku} já existe")

    agora = datetime.now(timezone.utc)
    await pool_bd.execute(
        """INSERT INTO products (id, sku, name, description, price, category_id, active, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, true, $7, $8)""",
        id_produto, requisicao.sku, requisicao.nome, requisicao.descricao, requisicao.preco, requisicao.id_categoria, agora, agora,
    )

    await cliente_redis.delete("produtos:lista:*")
    PRODUTOS_CRIADOS.inc()
    PRODUTOS_TOTAL.inc()
    
    logger.info("catalogo.criar_produto", extra={"id_produto": id_produto, "sku": requisicao.sku, "tempo_ms": cronometro.elapsed_ms})

    return RespostaProduto(
        id=id_produto, sku=requisicao.sku, nome=requisicao.nome, descricao=requisicao.descricao,
        preco=requisicao.preco, id_categoria=requisicao.id_categoria, nome_categoria=None, ativo=True,
        data_criacao=agora.isoformat(), data_atualizacao=agora.isoformat(),
    )


@app.patch("/catalogo/produtos/{id_produto}", response_model=RespostaProduto)
async def atualizar_produto(id_produto: str, requisicao: AtualizarProdutoRequisicao):
    cronometro = Timer()
    linha = await pool_bd.fetchrow("SELECT * FROM products WHERE id = $1", id_produto)
    
    if not linha:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    atualizacoes = []
    parametros = []
    numero_parametro = 1

    for campo, valor in requisicao.model_dump(exclude_none=True).items():
        atualizacoes.append(f"{campo} = ${numero_parametro}")
        parametros.append(valor)
        numero_parametro += 1

    if not atualizacoes:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    agora = datetime.now(timezone.utc)
    atualizacoes.append(f"updated_at = ${numero_parametro}")
    parametros.append(agora)
    parametros.append(id_produto)

    await pool_bd.execute(f"UPDATE products SET {', '.join(atualizacoes)} WHERE id = ${numero_parametro + 1}", *parametros)

    await cliente_redis.delete(f"produto:{id_produto}")
    await cliente_redis.delete("produtos:lista:*")
    PRODUTOS_ATUALIZADOS.inc()

    linha_atualizada = await pool_bd.fetchrow(
        """SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
                  c.name as category_name, p.active, p.created_at, p.updated_at
           FROM products p
           LEFT JOIN categories c ON p.category_id = c.id
           WHERE p.id = $1""",
        id_produto,
    )

    logger.info("catalogo.atualizar_produto", extra={"id_produto": id_produto, "tempo_ms": cronometro.elapsed_ms})
    return _converter_linha_produto(linha_atualizada)


@app.delete("/catalogo/produtos/{id_produto}", status_code=204)
async def deletar_produto(id_produto: str):
    cronometro = Timer()
    linha = await pool_bd.fetchrow("SELECT id FROM products WHERE id = $1", id_produto)
    
    if not linha:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    await pool_bd.execute("UPDATE products SET active = false, updated_at = NOW() WHERE id = $1", id_produto)
    
    await cliente_redis.delete(f"produto:{id_produto}")
    await cliente_redis.delete("produtos:lista:*")
    PRODUTOS_DELETADOS.inc()
    PRODUTOS_TOTAL.dec()
    
    logger.info("catalogo.deletar_produto", extra={"id_produto": id_produto, "tempo_ms": cronometro.elapsed_ms})


@app.get("/catalogo/categorias", response_model=List[RespostaCategoria])
async def listar_categorias():
    cronometro = Timer()
    chave_cache = "categorias:lista"
    
    em_cache = await cliente_redis.get(chave_cache)
    if em_cache:
        CACHE_ACERTOS.labels(tipo_recurso="categorias").inc()
        return json.loads(em_cache)

    CACHE_ERROS.labels(tipo_recurso="categorias").inc()
    linhas = await pool_bd.fetch("SELECT id, name, description, created_at FROM categories ORDER BY name")

    categorias = [
        RespostaCategoria(id=str(r["id"]), nome=r["name"], descricao=r["description"], data_criacao=r["created_at"].isoformat())
        for r in linhas
    ]

    await cliente_redis.setex(chave_cache, TTL_CACHE, json.dumps([c.model_dump() for c in categorias], default=str))
    logger.info("catalogo.listar_categorias", extra={"quantidade": len(categorias), "tempo_ms": cronometro.elapsed_ms})
    
    return categorias


@app.post("/catalogo/categorias", response_model=RespostaCategoria, status_code=201)
async def criar_categoria(requisicao: CriarCategoriaRequisicao):
    cronometro = Timer()
    id_categoria = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)

    await pool_bd.execute(
        "INSERT INTO categories (id, name, description, created_at) VALUES ($1, $2, $3, $4)",
        id_categoria, requisicao.nome, requisicao.descricao, agora,
    )

    await cliente_redis.delete("categorias:lista")
    logger.info("catalogo.criar_categoria", extra={"id_categoria": id_categoria, "nome": requisicao.nome, "tempo_ms": cronometro.elapsed_ms})

    return RespostaCategoria(id=id_categoria, nome=requisicao.nome, descricao=requisicao.descricao, data_criacao=agora.isoformat())


@app.get("/catalogo/pesquisar", response_model=List[RespostaProduto])
async def pesquisar_produtos(q: str = Query(..., min_length=2)):
    cronometro = Timer()
    termo_busca = f"%{q}%"

    linhas = await pool_bd.fetch(
        """SELECT p.id, p.sku, p.name, p.description, p.price, p.category_id,
                  c.name as category_name, p.active, p.created_at, p.updated_at
           FROM products p
           LEFT JOIN categories c ON p.category_id = c.id
           WHERE p.active = true AND (LOWER(p.name) LIKE LOWER($1) OR LOWER(p.sku) LIKE LOWER($1))
           LIMIT 50""",
        termo_busca,
    )

    logger.info("catalogo.pesquisar", extra={"termo": q, "resultados": len(linhas), "tempo_ms": cronometro.elapsed_ms})
    return [_converter_linha_produto(linha) for linha in linhas]


def _obter_template_rota(requisicao: Request) -> str:
    rota = requisicao.scope.get("route")
    return rota.path if rota and getattr(rota, "path", None) else requisicao.url.path


def _converter_linha_produto(linha) -> RespostaProduto:
    return RespostaProduto(
        id=str(linha["id"]), sku=linha["sku"], nome=linha["name"], descricao=linha["description"],
        preco=float(linha["price"]), id_categoria=str(linha["category_id"]) if linha["category_id"] else None,
        nome_categoria=linha["category_name"], ativo=linha["active"],
        data_criacao=linha["created_at"].isoformat(), data_atualizacao=linha["updated_at"].isoformat(),
    )
