// Cliente da API de Sugestões com timeout + fallback.
// Princípio de resiliência: sugestão é OPCIONAL. Se falhar/expirar,
// a compra segue normalmente — nunca propagamos o erro pra cima.

const BASE = process.env.SUGESTOES_URL ?? "http://localhost:4002";
const TIMEOUT_MS = Number(process.env.SUGESTOES_TIMEOUT_MS ?? 800);

export interface Sugestao {
  produto: string;
  motivo: string;
}

export interface ResultadoSugestao {
  ok: boolean;
  itens: Sugestao[];
  fonte: "servico" | "fallback";
  erro?: string;
}

export async function buscarSugestoes(
  produto: string
): Promise<ResultadoSugestao> {
  const tentativas = 3;
  for (let i = 0; i < tentativas; i++) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    try {
      const resp = await fetch(
        `${BASE}/sugestoes?produto=${encodeURIComponent(produto)}`,
        { signal: ctrl.signal }
      );
      if (!resp.ok) throw new Error(`status ${resp.status}`);
      const data = (await resp.json()) as { itens: Sugestao[] };
      return { ok: true, itens: data.itens ?? [], fonte: "servico" };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (i === tentativas - 1) {
        // Degradação graciosa: log e segue sem sugestões.
        console.warn(`[sugestoes] indisponível (${msg}) após ${tentativas} tentativas — seguindo sem sugestão`);
        return { ok: false, itens: [], fonte: "fallback", erro: msg };
      }
      console.log(`[sugestoes] tentativa ${i + 1} falhou (${msg}), tentando novamente em 100ms...`);
      await new Promise((r) => setTimeout(r, 100));
    } finally {
      clearTimeout(t);
    }
  }
  return { ok: false, itens: [], fonte: "fallback", erro: "Tentativas de retry esgotadas" };
}
