import { useEffect, useState, type CSSProperties } from "react";
import {
  criarCompra,
  listarCompras,
  getChaos,
  setChaos,
  type Compra,
  type RespostaCompra,
  type ChaosState,
} from "./api";
import "./App.css";

// UUID v4 (usa crypto nativo do browser).
const novaChave = () => crypto.randomUUID();

export default function App() {
  const [produto, setProduto] = useState("notebook");
  const [quantidade, setQuantidade] = useState(1);
  const [valor, setValor] = useState(3500);

  // Chave de idempotência: gerada automaticamente e rotacionada após cada
  // resposta do backend (sucesso ou replay) — cada compra concluída começa
  // uma nova "intenção" com chave nova.
  const [chave, setChave] = useState(novaChave());

  const [compras, setCompras] = useState<Compra[]>([]);
  const [ultima, setUltima] = useState<RespostaCompra | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  // --- Estado de caos + métricas de resiliência ---------------------------
  const [chaos, setChaosState] = useState<ChaosState | null>(null);
  const [sugOnline, setSugOnline] = useState<boolean>(true);
  const [metricas, setMetricas] = useState({
    comprasOk: 0,
    sugestoesOk: 0,
    sugestoesCaidas: 0,
  });

  async function refresh() {
    try {
      setCompras(await listarCompras());
    } catch (e) {
      setErro(String(e));
    }
  }

  // Lê o estado do caos no sugestões (e detecta se está online).
  async function refreshChaos() {
    try {
      setChaosState(await getChaos());
      setSugOnline(true);
    } catch {
      setSugOnline(false);
    }
  }

  useEffect(() => {
    refresh();
    refreshChaos();
    // poll leve do estado do caos/saúde do sugestões
    const t = setInterval(refreshChaos, 3000);
    return () => clearInterval(t);
  }, []);

  async function aplicarChaos(patch: Partial<ChaosState>) {
    try {
      setChaosState(await setChaos(patch));
      setSugOnline(true);
    } catch (e) {
      setErro(String(e));
    }
  }

  async function enviar() {
    setErro(null);
    try {
      const resp = await criarCompra({
        produto,
        quantidade,
        valor_total: valor,
        idempotencyKey: chave,
      });
      setUltima(resp);
      // Métricas: compra sempre conta como OK (crítica sobreviveu).
      // Sugestão conta separado conforme veio do serviço ou do fallback.
      setMetricas((m) => ({
        comprasOk: m.comprasOk + 1,
        sugestoesOk: m.sugestoesOk + (resp.sugestao.fonte === "servico" ? 1 : 0),
        sugestoesCaidas:
          m.sugestoesCaidas + (resp.sugestao.fonte === "fallback" ? 1 : 0),
      }));
      // Rotaciona a chave: próxima compra usa uma nova intenção.
      setChave(novaChave());
      await refresh();
    } catch (e) {
      setErro(String(e));
    }
  }

  const caosLigado = !!chaos && (chaos.failRate > 0 || chaos.latencyMs > 0);

  return (
    <div style={s.page}>
      <h1>🧪 Lab: Engenharia do Caos & Idempotência</h1>

      {/* ---- Painel de Caos -------------------------------------------- */}
      <section style={{ ...s.card, ...s.chaosCard }}>
        <div style={s.chaosHeader}>
          <h2 style={{ margin: 0 }}>🔥 Painel de Caos</h2>
          {!sugOnline ? (
            <span style={s.badgeOff}>API Sugestões OFFLINE</span>
          ) : caosLigado ? (
            <span style={s.badgeCaos}>
              CAOS ATIVO — falha {Math.round((chaos?.failRate ?? 0) * 100)}% ·
              latência {chaos?.latencyMs ?? 0}ms
            </span>
          ) : (
            <span style={s.badgeOk}>normal</span>
          )}
        </div>

        <p style={{ color: "#666", margin: "8px 0" }}>
          Injeta falha/latência na API de Sugestões (opcional). A de Compras
          (crítica) deve continuar funcionando.
        </p>

        <div style={s.row}>
          <button onClick={() => aplicarChaos({ failRate: 0, latencyMs: 0 })}>
            ✅ Normal
          </button>
          <button onClick={() => aplicarChaos({ failRate: 1 })}>
            💥 Falha 100%
          </button>
        </div>
      </section>

      {/* ---- Métricas de resiliência ----------------------------------- */}
      <section style={s.card}>
        <h2>📊 Resiliência (sessão)</h2>
        <div style={s.metricRow}>
          <div style={{ ...s.metric, ...s.metricGood }}>
            <div style={s.metricNum}>{metricas.comprasOk}</div>
            <div style={s.metricLabel}>compras OK</div>
          </div>
          <div style={s.metric}>
            <div style={s.metricNum}>{metricas.sugestoesOk}</div>
            <div style={s.metricLabel}>sugestões online</div>
          </div>
          <div style={{ ...s.metric, ...s.metricBad }}>
            <div style={s.metricNum}>{metricas.sugestoesCaidas}</div>
            <div style={s.metricLabel}>sugestões caídas</div>
          </div>
        </div>
        <small style={{ color: "#666" }}>
          Mesmo com sugestões caindo, <strong>compras OK</strong> sobe a cada
          envio. É a degradação graciosa em números.
        </small>
      </section>

      <section style={s.card}>
        <h2>Nova compra</h2>
        <div style={s.row}>
          <label>
            Produto{" "}
            <input
              value={produto}
              onChange={(e) => setProduto(e.target.value)}
            />
          </label>
          <label>
            Qtd{" "}
            <input
              type="number"
              value={quantidade}
              min={1}
              onChange={(e) => setQuantidade(Number(e.target.value))}
              style={{ width: 60 }}
            />
          </label>
          <label>
            Valor{" "}
            <input
              type="number"
              value={valor}
              onChange={(e) => setValor(Number(e.target.value))}
              style={{ width: 90 }}
            />
          </label>
        </div>

        <div style={s.keyBox}>
          <span>
            <strong>Idempotency-Key:</strong>{" "}
            <code style={{ fontSize: 12 }}>{chave}</code>
          </span>
          <small style={{ color: "#999" }}>
            rotaciona sozinha a cada compra concluída
          </small>
        </div>

        <div style={s.row}>
          <button onClick={enviar}>Enviar compra</button>
          <small style={{ color: "#666" }}>
            Backend leva ~3s. Clique várias vezes seguidas: mesma chave → uma
            só compra (idempotência).
          </small>
        </div>

        {erro && <p style={{ color: "crimson" }}>Erro: {erro}</p>}
      </section>

      {ultima && (
        <section style={s.card}>
          <h2>Resultado</h2>
          <p>
            Compra <code>{ultima.compra.id.slice(0, 8)}</code> —{" "}
            {ultima.replay ? (
              <span style={s.badgeReplay}>REPLAY idempotente (não duplicou)</span>
            ) : (
              <span style={s.badgeNova}>criada agora</span>
            )}
          </p>

          {/* Widget de sugestões: degrada se serviço caiu */}
          <div style={s.sug}>
            <strong>Sugestões</strong>{" "}
            {ultima.sugestao.fonte === "servico" ? (
              <span style={s.badgeOk}>online</span>
            ) : (
              <span style={s.badgeOff}>indisponível — compra seguiu normal</span>
            )}
            {ultima.sugestao.itens.length > 0 ? (
              <ul>
                {ultima.sugestao.itens.map((it, i) => (
                  <li key={i}>
                    {it.produto} <em style={{ color: "#888" }}>({it.motivo})</em>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "#888" }}>Sem sugestões no momento.</p>
            )}
          </div>
        </section>
      )}

      <section style={s.card}>
        <h2>Compras ({compras.length})</h2>
        <button onClick={refresh}>Atualizar</button>
        <ul>
          {compras.map((c) => (
            <li key={c.id}>
              <code>{c.id.slice(0, 8)}</code> — {c.produto} ×{c.quantidade} = R$
              {Number(c.valor_total).toFixed(2)}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

const s: Record<string, CSSProperties> = {
  page: {
    maxWidth: 720,
    margin: "40px auto",
    fontFamily: "system-ui, sans-serif",
    padding: "0 16px",
  },
  card: {
    border: "1px solid #ddd",
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
  },
  chaosCard: { borderColor: "#f0a", background: "#fff5fb" },
  chaosHeader: {
    display: "flex",
    gap: 12,
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
  },
  row: { display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" },
  keyBox: {
    display: "flex",
    gap: 12,
    alignItems: "center",
    justifyContent: "space-between",
    background: "#f6f6f6",
    padding: 8,
    borderRadius: 6,
    margin: "12px 0",
    flexWrap: "wrap",
  },
  sug: { background: "#fafafa", padding: 12, borderRadius: 6, marginTop: 8 },
  metricRow: { display: "flex", gap: 12, flexWrap: "wrap", margin: "8px 0" },
  metric: {
    flex: "1 1 120px",
    textAlign: "center",
    border: "1px solid #eee",
    borderRadius: 8,
    padding: 12,
    background: "#fafafa",
  },
  metricGood: { borderColor: "#9ec5a0", background: "#eef7ef" },
  metricBad: { borderColor: "#e0a0a0", background: "#fbeeee" },
  metricNum: { fontSize: 32, fontWeight: 700 },
  metricLabel: { fontSize: 12, color: "#666" },
  badgeReplay: { background: "#fff3cd", padding: "2px 8px", borderRadius: 4 },
  badgeNova: { background: "#d1e7dd", padding: "2px 8px", borderRadius: 4 },
  badgeCaos: {
    background: "#ffe0ef",
    color: "#c0006a",
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 13,
    fontWeight: 600,
  },
  badgeOk: { color: "#0a0", fontSize: 12 },
  badgeOff: {
    color: "#fff",
    background: "#c00",
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 12,
  },
};
