import { createHash } from "node:crypto";
import type { Request, Response, NextFunction } from "express";
import { pool } from "./db.js";

// UUID v4 loose check
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function hashBody(body: unknown): string {
  return createHash("sha256").update(JSON.stringify(body ?? {})).digest("hex");
}

/**
 * Middleware de idempotência para POST.
 *
 * Fluxo:
 *  1. Lê header `Idempotency-Key` (UUID).
 *  2. Se chave já existe e bate o hash do body -> devolve resposta salva (replay).
 *  3. Se chave existe mas body difere -> 422 (uso errado da chave).
 *  4. Se chave nova -> reserva a chave, deixa o handler rodar, e
 *     intercepta res.json para persistir status+body sob a chave.
 *
 * Resultado: retry de rede com a MESMA chave nunca duplica a compra.
 */
export async function idempotency(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  const key = req.header("Idempotency-Key");

  if (!key || !UUID_RE.test(key)) {
    res
      .status(400)
      .json({ erro: "Header 'Idempotency-Key' (UUID) obrigatório" });
    return;
  }

  const reqHash = hashBody(req.body);

  // 1) Já existe?
  const existing = await pool.query(
    "SELECT request_hash, response_status, response_body FROM idempotency_keys WHERE key = $1",
    [key]
  );

  if (existing.rowCount && existing.rowCount > 0) {
    const row = existing.rows[0];
    if (row.request_hash !== reqHash) {
      res.status(422).json({
        erro: "Idempotency-Key reutilizada com payload diferente",
      });
      return;
    }
    // Replay: ainda processando (sem resposta gravada) ou já concluída.
    if (row.response_status == null) {
      res.status(409).json({ erro: "Requisição original ainda em processamento" });
      return;
    }
    res.set("Idempotent-Replay", "true");
    res.status(row.response_status).json(row.response_body);
    return;
  }

  // 2) Reserva a chave (response_status null = "em andamento").
  //    ON CONFLICT cobre corrida entre dois requests simultâneos.
  const reserved = await pool.query(
    `INSERT INTO idempotency_keys (key, request_hash)
     VALUES ($1, $2)
     ON CONFLICT (key) DO NOTHING`,
    [key, reqHash]
  );
  if (reserved.rowCount === 0) {
    res.status(409).json({ erro: "Requisição concorrente com mesma chave" });
    return;
  }

  // 3) Intercepta res.json para persistir o resultado sob a chave.
  const originalJson = res.json.bind(res);
  res.json = (body: unknown) => {
    pool
      .query(
        "UPDATE idempotency_keys SET response_status = $2, response_body = $3 WHERE key = $1",
        [key, res.statusCode, body]
      )
      .catch((e) => console.error("[idempotency] falha ao gravar resposta", e));
    return originalJson(body);
  };

  next();
}
