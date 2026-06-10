import "dotenv/config";
import express from "express";
import type { Request, Response } from "express";
import { pool, waitForDb } from "./db.js";
import { migrate } from "./migrate.js";
import { idempotency } from "./idempotency.js";
import { buscarSugestoes } from "./sugestoes.js";

const app = express();
app.use(express.json());

// CORS aberto (lab). Em prod, restringir origem.
app.use((_req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.header(
    "Access-Control-Allow-Headers",
    "Content-Type,Idempotency-Key"
  );
  res.header("Access-Control-Expose-Headers", "Idempotent-Replay");
  if (_req.method === "OPTIONS") {
    res.sendStatus(204);
    return;
  }
  next();
});

app.get("/health", (_req, res) => {
  res.json({ ok: true, servico: "compras" });
});

app.get("/compras", async (_req: Request, res: Response) => {
  const r = await pool.query(
    "SELECT * FROM compras ORDER BY criado_em DESC LIMIT 50"
  );
  res.json(r.rows);
});

// POST /compras — protegido por idempotência.
app.post("/compras", idempotency, async (req: Request, res: Response) => {
  const { produto, quantidade, valor_total } = req.body ?? {};

  if (
    typeof produto !== "string" ||
    !Number.isInteger(quantidade) ||
    quantidade <= 0 ||
    typeof valor_total !== "number"
  ) {
    res.status(400).json({ erro: "payload inválido" });
    return;
  }

  // Atraso artificial: dá tempo de demonstrar idempotência (cliques repetidos
  // durante o processamento) e o estado de carregamento no front.
  await new Promise((r) => setTimeout(r, 3000));

  const r = await pool.query(
    `INSERT INTO compras (produto, quantidade, valor_total)
     VALUES ($1, $2, $3) RETURNING *`,
    [produto, quantidade, valor_total]
  );
  const compra = r.rows[0];

  // Sugestão é best-effort: se cair, compra segue (resiliência).
  const sugestao = await buscarSugestoes(produto);

  res.status(201).json({ compra, sugestao });
});

const PORT = Number(process.env.PORT ?? 4001);

waitForDb()
  .then(() => migrate()) // aplica migrations pendentes antes de servir
  .then(() => {
    app.listen(PORT, () =>
      console.log(`[compras] ouvindo na porta ${PORT}`)
    );
  })
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });
