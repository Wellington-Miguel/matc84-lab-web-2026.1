import "dotenv/config";
import express from "express";
import type { Request, Response, NextFunction } from "express";

const app = express();
app.use(express.json());

app.use((_req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Methods", "GET,PUT,OPTIONS");
  res.header("Access-Control-Allow-Headers", "Content-Type");
  if (_req.method === "OPTIONS") {
    res.sendStatus(204);
    return;
  }
  next();
});

// ---- Estado de caos (ajustável em runtime) ---------------------------------
const chaos = {
  failRate: Number(process.env.CHAOS_FAIL_RATE ?? 0), // 0..1 -> prob. de 500
  latencyMs: Number(process.env.CHAOS_LATENCY_MS ?? 0), // atraso fixo injetado
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Middleware que injeta falha/latência ANTES do handler real.
async function chaosMiddleware(
  _req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  if (chaos.latencyMs > 0) await sleep(chaos.latencyMs);
  if (chaos.failRate > 0 && Math.random() < chaos.failRate) {
    res.status(500).json({ erro: "caos injetado: falha simulada" });
    return;
  }
  next();
}

// ---- Endpoints de controle (NÃO sofrem caos) -------------------------------
app.get("/health", (_req, res) => {
  res.json({ ok: true, servico: "sugestoes", chaos });
});

// Ajusta caos ao vivo durante a demo. Ex:
//   curl -X PUT localhost:4002/chaos -H 'Content-Type: application/json' \
//        -d '{"failRate":1,"latencyMs":0}'
app.put("/chaos", (req, res) => {
  const { failRate, latencyMs } = req.body ?? {};
  if (typeof failRate === "number") chaos.failRate = Math.min(1, Math.max(0, failRate));
  if (typeof latencyMs === "number") chaos.latencyMs = Math.max(0, latencyMs);
  console.log("[chaos] atualizado:", chaos);
  res.json({ ok: true, chaos });
});

// ---- Endpoint real (sofre caos) --------------------------------------------
const CATALOGO: Record<string, { produto: string; motivo: string }[]> = {
  notebook: [
    { produto: "Mouse sem fio", motivo: "Acompanha notebook" },
    { produto: "Mochila", motivo: "Transporte" },
  ],
  cafe: [
    { produto: "Filtro de papel", motivo: "Complemento" },
    { produto: "Açúcar", motivo: "Vai junto" },
  ],
};

app.get("/sugestoes", chaosMiddleware, (req: Request, res: Response) => {
  const produto = String(req.query.produto ?? "").toLowerCase();
  const itens =
    CATALOGO[produto] ??
    [{ produto: "Item popular", motivo: "Mais vendido" }];
  res.json({ itens });
});

const PORT = Number(process.env.PORT ?? 4002);
app.listen(PORT, () =>
  console.log(`[sugestoes] ouvindo na porta ${PORT} | chaos:`, chaos)
);
