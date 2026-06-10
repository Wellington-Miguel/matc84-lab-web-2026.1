const COMPRAS_URL =
  (import.meta.env.VITE_COMPRAS_URL as string) ?? "http://localhost:4001";
const SUGESTOES_URL =
  (import.meta.env.VITE_SUGESTOES_URL as string) ?? "http://localhost:4002";

export interface Compra {
  id: string;
  produto: string;
  quantidade: number;
  valor_total: number;
  criado_em: string;
}

export interface Sugestao {
  produto: string;
  motivo: string;
}

export interface RespostaCompra {
  compra: Compra;
  // sugestao vem da api-compras (best-effort). Pode ter ok:false (fallback).
  sugestao: {
    ok: boolean;
    itens: Sugestao[];
    fonte: "servico" | "fallback";
    erro?: string;
  };
  replay: boolean; // true se foi resposta idempotente (replay)
}

export async function listarCompras(): Promise<Compra[]> {
  const r = await fetch(`${COMPRAS_URL}/compras`);
  if (!r.ok) throw new Error(`GET /compras -> ${r.status}`);
  return r.json();
}

export async function criarCompra(input: {
  produto: string;
  quantidade: number;
  valor_total: number;
  idempotencyKey: string;
}): Promise<RespostaCompra> {
  const r = await fetch(`${COMPRAS_URL}/compras`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": input.idempotencyKey,
    },
    body: JSON.stringify({
      produto: input.produto,
      quantidade: input.quantidade,
      valor_total: input.valor_total,
    }),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body?.erro ?? `POST /compras -> ${r.status}`);
  return { ...body, replay: r.headers.get("Idempotent-Replay") === "true" };
}

// ---- Controle de caos (fala direto com a API de Sugestões) -----------------

export interface ChaosState {
  failRate: number; // 0..1 — probabilidade de retornar 500
  latencyMs: number; // atraso fixo injetado
}

// Lê estado atual do caos. Lança se o serviço estiver fora (útil pra badge).
export async function getChaos(): Promise<ChaosState> {
  const r = await fetch(`${SUGESTOES_URL}/health`);
  if (!r.ok) throw new Error(`GET /health -> ${r.status}`);
  const data = (await r.json()) as { chaos: ChaosState };
  return data.chaos;
}

// Ajusta o caos ao vivo. Aceita parcial (só failRate, só latencyMs, etc.).
export async function setChaos(
  patch: Partial<ChaosState>
): Promise<ChaosState> {
  const r = await fetch(`${SUGESTOES_URL}/chaos`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`PUT /chaos -> ${r.status}`);
  const data = (await r.json()) as { chaos: ChaosState };
  return data.chaos;
}
