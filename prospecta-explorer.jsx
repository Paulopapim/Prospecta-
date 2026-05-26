import { useState } from "react";

const DB_SCHEMA = {
  usuarios: {
    columns: [
      { name: "id", type: "INTEGER", pk: true, desc: "Auto-incremento" },
      { name: "username", type: "TEXT", unique: true, desc: "Login do usuário" },
      { name: "senha", type: "TEXT", desc: "Hash PBKDF2 (salt$hash)" },
      { name: "is_admin", type: "INTEGER", desc: "1 = admin, 0 = operador" },
      { name: "criado_em", type: "TEXT/TIMESTAMP", desc: "Data de criação" },
    ],
    rows: [
      { id: 1, username: "admin", is_admin: 1, criado_em: "2026-05-18 22:47:05" },
      { id: 2, username: "paulocesarpapim@gmail.com", is_admin: 1, criado_em: "2026-05-18 22:54:50" },
    ],
  },
  config: {
    columns: [
      { name: "chave", type: "TEXT", pk: true, desc: "Identificador da config" },
      { name: "valor", type: "TEXT", desc: "Valor armazenado" },
    ],
    rows: [
      { chave: "api_key", valor: "aa26c13a...dc219ab (128 chars)" },
    ],
  },
};

const API_ROUTES = [
  { method: "GET", path: "/", auth: false, desc: "Página principal — retorna HTML de login ou app", section: "Auth" },
  { method: "POST", path: "/api/login", auth: false, desc: "Autentica usuário (username + senha)", section: "Auth", body: '{ "username": "...", "senha": "..." }' },
  { method: "POST", path: "/api/logout", auth: true, desc: "Encerra a sessão", section: "Auth" },
  { method: "GET", path: "/api/eu", auth: true, desc: "Dados do usuário logado", section: "Auth" },
  { method: "GET", path: "/api/admin/usuarios", auth: true, admin: true, desc: "Lista todos os usuários", section: "Usuários" },
  { method: "POST", path: "/api/admin/usuarios", auth: true, admin: true, desc: "Cria novo usuário", section: "Usuários", body: '{ "username": "...", "senha": "...", "is_admin": false }' },
  { method: "DELETE", path: "/api/admin/usuarios/:id", auth: true, admin: true, desc: "Remove usuário por ID", section: "Usuários" },
  { method: "PUT", path: "/api/admin/usuarios/:id/senha", auth: true, admin: true, desc: "Altera senha de usuário", section: "Usuários", body: '{ "senha": "..." }' },
  { method: "GET", path: "/api/admin/apikey", auth: true, admin: true, desc: "Retorna API KEY salva", section: "Config" },
  { method: "POST", path: "/api/admin/apikey", auth: true, admin: true, desc: "Salva nova API KEY", section: "Config", body: '{ "api_key": "..." }' },
  { method: "GET", path: "/api/admin/logs", auth: true, admin: true, desc: "Retorna logs do sistema", section: "Logs" },
  { method: "DELETE", path: "/api/admin/logs", auth: true, admin: true, desc: "Limpa todos os logs", section: "Logs" },
  { method: "POST", path: "/api/saldo", auth: true, desc: "Consulta saldo na Casa dos Dados", section: "API Externa" },
  { method: "POST", path: "/api/previa", auth: true, desc: "Pesquisa prévia de CNPJs (até 10 resultados)", section: "API Externa", body: '{ "cnae": "6920601", "situacao": "ATIVA", "ufs": "SP", ... }' },
  { method: "POST", path: "/api/captar", auth: true, desc: "Gera arquivo CSV via Casa dos Dados", section: "API Externa", body: '{ "cnae": "...", "nome": "captacao", ... }' },
  { method: "GET", path: "/api/solicitacoes", auth: true, desc: "Lista arquivos gerados", section: "API Externa" },
  { method: "GET", path: "/api/baixar-solicitacao/:uuid", auth: true, desc: "Baixa arquivo ZIP/CSV gerado", section: "API Externa" },
  { method: "GET", path: "/api/debug-arquivo/:uuid", auth: true, admin: true, desc: "Debug — testa 3 endpoints para UUID", section: "Debug" },
];

const FILES = [
  { name: "app.py", lines: "~650", desc: "Flask app principal — rotas, HTML inline, lógica de API", icon: "🐍" },
  { name: "db.py", lines: "~170", desc: "Camada de dados — SQLite/Postgres, hash de senhas, CRUD", icon: "🗄️" },
  { name: "captador.db", size: "24 KB", desc: "Banco SQLite local com usuários e config", icon: "💾" },
  { name: "requirements.txt", lines: "3", desc: "flask, requests, gunicorn, psycopg[binary]", icon: "📦" },
  { name: "render.yaml", lines: "~15", desc: "Config de deploy para Render.com", icon: "☁️" },
  { name: "DEPLOY.md", lines: "~100", desc: "Guia de publicação no Render", icon: "📖" },
  { name: "GUIA.md", lines: "~90", desc: "Guia geral de uso", icon: "📖" },
  { name: "MIGRACAO-POSTGRES.md", lines: "~70", desc: "Como migrar de SQLite para Postgres", icon: "📖" },
];

const EXTERNAL_ENDPOINTS = [
  { name: "Pesquisa CNPJ (v5)", url: "api.casadosdados.com.br/v5/cnpj/pesquisa", desc: "Busca CNPJs com filtros" },
  { name: "Gerar arquivo (v5)", url: "api.casadosdados.com.br/v5/cnpj/pesquisa/arquivo", desc: "Solicita geração de CSV" },
  { name: "Listar arquivos (v4)", url: "api.casadosdados.com.br/v4/cnpj/pesquisa/arquivo", desc: "Lista solicitações feitas" },
  { name: "Download (v4 public)", url: "api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo/:uuid", desc: "Baixa o CSV/ZIP gerado" },
  { name: "Saldo (v5)", url: "api.casadosdados.com.br/v5/saldo", desc: "Consulta créditos disponíveis" },
];

const PESQUISA_PARAMS = [
  { param: "cnae", desc: "CNAE(s) separados por vírgula", exemplo: "6920601" },
  { param: "situacao", desc: "Situação cadastral", exemplo: "ATIVA | BAIXADA | INAPTA | SUSPENSA" },
  { param: "ufs", desc: "UF(s) separadas por vírgula", exemplo: "SP,RJ" },
  { param: "municipios", desc: "Município(s)", exemplo: "sao paulo,campinas" },
  { param: "ultimos_dias", desc: "Empresas abertas nos últimos N dias", exemplo: "30" },
  { param: "total_linhas", desc: "Limite de resultados (1–1000)", exemplo: "100" },
  { param: "somente_mei", desc: "Filtra só MEI", exemplo: "true/false" },
  { param: "com_telefone", desc: "Só com telefone", exemplo: "true/false" },
  { param: "com_email", desc: "Só com e-mail", exemplo: "true/false" },
];

const methodColor = (m) => {
  const map = { GET: "#22c55e", POST: "#3b82f6", PUT: "#f59e0b", DELETE: "#ef4444" };
  return map[m] || "#94a3b8";
};

const Badge = ({ children, color = "#3b82f6", bg }) => (
  <span style={{
    display: "inline-block", padding: "2px 10px", borderRadius: 20,
    fontSize: 11, fontWeight: 700, letterSpacing: ".03em",
    background: bg || `${color}18`, color, border: `1px solid ${color}30`,
  }}>{children}</span>
);

export default function App() {
  const [tab, setTab] = useState("overview");
  const [expandedRoute, setExpandedRoute] = useState(null);
  const [dbTable, setDbTable] = useState("usuarios");
  const [searchRoutes, setSearchRoutes] = useState("");

  const tabs = [
    { id: "overview", label: "Visão Geral", icon: "◈" },
    { id: "database", label: "Banco de Dados", icon: "⬡" },
    { id: "routes", label: "Rotas da API", icon: "⟶" },
    { id: "external", label: "APIs Externas", icon: "◎" },
    { id: "filters", label: "Filtros de Pesquisa", icon: "⊞" },
  ];

  const filteredRoutes = API_ROUTES.filter(r =>
    !searchRoutes ||
    r.path.toLowerCase().includes(searchRoutes.toLowerCase()) ||
    r.desc.toLowerCase().includes(searchRoutes.toLowerCase()) ||
    r.method.toLowerCase().includes(searchRoutes.toLowerCase())
  );

  const routeSections = [...new Set(filteredRoutes.map(r => r.section))];

  return (
    <div style={{
      fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace",
      background: "#0a0e17", color: "#c4cede", minHeight: "100vh",
      maxWidth: 920, margin: "0 auto", padding: "28px 20px",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e2d45; border-radius: 3px; }
      `}</style>

      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 6 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: "#e8ecf4", letterSpacing: "-0.02em" }}>
            Prospecta<span style={{ color: "#6d8cff" }}>.</span>explorer
          </h1>
          <span style={{
            fontSize: 10, color: "#3b5998", background: "#131b2e",
            padding: "3px 10px", borderRadius: 4, fontWeight: 600,
          }}>CNPJ Captador</span>
        </div>
        <p style={{ fontSize: 12, color: "#445570", lineHeight: 1.6 }}>
          Estrutura completa do projeto — banco, rotas, APIs e filtros de consulta
        </p>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex", gap: 2, marginBottom: 28, flexWrap: "wrap",
        background: "#0d1220", borderRadius: 10, padding: 4,
        border: "1px solid #151d2e",
      }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            flex: 1, minWidth: 120, padding: "10px 8px", border: "none", borderRadius: 8,
            background: tab === t.id ? "#161f35" : "transparent",
            color: tab === t.id ? "#8aabff" : "#3a4a66",
            fontFamily: "inherit", fontSize: 11.5, fontWeight: 600,
            cursor: "pointer", transition: "all .2s",
            boxShadow: tab === t.id ? "0 0 0 1px #1e2d4580" : "none",
          }}>
            <span style={{ marginRight: 6, fontSize: 13 }}>{t.icon}</span>{t.label}
          </button>
        ))}
      </div>

      {/* OVERVIEW */}
      {tab === "overview" && (
        <div>
          <div style={{
            background: "linear-gradient(135deg, #0f1628 0%, #131d33 100%)",
            border: "1px solid #1a2540", borderRadius: 14, padding: 24, marginBottom: 20,
          }}>
            <div style={{ fontSize: 11, color: "#3b5998", fontWeight: 700, marginBottom: 14, textTransform: "uppercase", letterSpacing: ".08em" }}>
              Arquitetura
            </div>
            <div style={{ fontSize: 13, color: "#7a8caa", lineHeight: 1.8 }}>
              App Flask single-file com HTML inline. Usa <b style={{ color: "#8aabff" }}>SQLite</b> localmente
              e <b style={{ color: "#8aabff" }}>PostgreSQL</b> em produção (auto-detecção via DATABASE_URL).
              Autenticação por sessão Flask. Integração com a API da <b style={{ color: "#8aabff" }}>Casa dos Dados</b> para
              pesquisa e exportação de CNPJs. Deploy configurado para <b style={{ color: "#8aabff" }}>Render.com</b>.
            </div>
          </div>

          {/* Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, marginBottom: 24 }}>
            {[
              { label: "Arquivos", val: "8", color: "#6d8cff" },
              { label: "Rotas API", val: String(API_ROUTES.length), color: "#22c55e" },
              { label: "Tabelas DB", val: "2", color: "#f59e0b" },
              { label: "Usuários", val: "2", color: "#a78bfa" },
              { label: "APIs Externas", val: "5", color: "#f472b6" },
            ].map(s => (
              <div key={s.label} style={{
                background: "#0d1220", border: "1px solid #151d2e", borderRadius: 10, padding: "16px 14px",
              }}>
                <div style={{ fontSize: 10, color: "#3a4a66", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 6 }}>{s.label}</div>
                <div style={{ fontSize: 26, fontWeight: 700, color: s.color }}>{s.val}</div>
              </div>
            ))}
          </div>

          {/* Files */}
          <div style={{ fontSize: 11, color: "#3b5998", fontWeight: 700, marginBottom: 12, textTransform: "uppercase", letterSpacing: ".08em" }}>
            Arquivos do Projeto
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {FILES.map(f => (
              <div key={f.name} style={{
                display: "flex", alignItems: "center", gap: 12,
                background: "#0d1220", border: "1px solid #151d2e", borderRadius: 8, padding: "10px 14px",
              }}>
                <span style={{ fontSize: 18, width: 28, textAlign: "center" }}>{f.icon}</span>
                <div style={{ flex: 1 }}>
                  <span style={{ fontWeight: 600, color: "#c4cede", fontSize: 12.5 }}>{f.name}</span>
                  <span style={{ color: "#2a3a56", margin: "0 8px" }}>—</span>
                  <span style={{ color: "#4a5a76", fontSize: 12 }}>{f.desc}</span>
                </div>
                {f.lines && <span style={{ fontSize: 10, color: "#2a3a56" }}>{f.lines} linhas</span>}
                {f.size && <span style={{ fontSize: 10, color: "#2a3a56" }}>{f.size}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* DATABASE */}
      {tab === "database" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            {Object.keys(DB_SCHEMA).map(t => (
              <button key={t} onClick={() => setDbTable(t)} style={{
                padding: "8px 18px", border: "none", borderRadius: 8,
                background: dbTable === t ? "#161f35" : "#0d1220",
                color: dbTable === t ? "#8aabff" : "#3a4a66",
                fontFamily: "inherit", fontSize: 12, fontWeight: 600,
                cursor: "pointer", transition: "all .2s",
                boxShadow: dbTable === t ? "0 0 0 1px #1e2d4580" : "none",
              }}>
                {t}
              </button>
            ))}
          </div>

          {/* Schema */}
          <div style={{
            background: "#0d1220", border: "1px solid #151d2e", borderRadius: 12,
            padding: 20, marginBottom: 16,
          }}>
            <div style={{ fontSize: 11, color: "#3b5998", fontWeight: 700, marginBottom: 14, textTransform: "uppercase", letterSpacing: ".08em" }}>
              Esquema — {dbTable}
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1a2540" }}>
                    {["Coluna", "Tipo", "Atributos", "Descrição"].map(h => (
                      <th key={h} style={{
                        textAlign: "left", padding: "8px 10px", color: "#3a4a66",
                        fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".06em",
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {DB_SCHEMA[dbTable].columns.map(c => (
                    <tr key={c.name} style={{ borderBottom: "1px solid #111827" }}>
                      <td style={{ padding: "8px 10px", fontWeight: 600, color: "#c4cede" }}>{c.name}</td>
                      <td style={{ padding: "8px 10px" }}><Badge color="#f59e0b">{c.type}</Badge></td>
                      <td style={{ padding: "8px 10px" }}>
                        {c.pk && <Badge color="#ef4444">PK</Badge>}
                        {c.unique && <span style={{ marginLeft: 4 }}><Badge color="#a78bfa">UNIQUE</Badge></span>}
                      </td>
                      <td style={{ padding: "8px 10px", color: "#4a5a76" }}>{c.desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Data */}
          <div style={{
            background: "#0d1220", border: "1px solid #151d2e", borderRadius: 12, padding: 20,
          }}>
            <div style={{ fontSize: 11, color: "#3b5998", fontWeight: 700, marginBottom: 14, textTransform: "uppercase", letterSpacing: ".08em" }}>
              Dados atuais — {DB_SCHEMA[dbTable].rows.length} registro(s)
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1a2540" }}>
                    {Object.keys(DB_SCHEMA[dbTable].rows[0] || {}).map(k => (
                      <th key={k} style={{
                        textAlign: "left", padding: "8px 10px", color: "#3a4a66",
                        fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".06em",
                      }}>{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {DB_SCHEMA[dbTable].rows.map((r, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #111827" }}>
                      {Object.values(r).map((v, j) => (
                        <td key={j} style={{ padding: "8px 10px", color: "#8a9ab6", wordBreak: "break-all", maxWidth: 260 }}>
                          {typeof v === "number" ? <span style={{ color: "#6d8cff" }}>{v}</span> : String(v)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div style={{
            marginTop: 16, background: "#0c1424", border: "1px solid #1a253a", borderRadius: 10,
            padding: "14px 16px", fontSize: 12, color: "#4a5a76", lineHeight: 1.6,
          }}>
            <b style={{ color: "#6d8cff" }}>Nota:</b> Senhas são armazenadas com hash PBKDF2-SHA256 + salt aleatório de 16 bytes.
            A detecção SQLite/Postgres é automática via variável <code style={{ color: "#8aabff" }}>DATABASE_URL</code>.
          </div>
        </div>
      )}

      {/* ROUTES */}
      {tab === "routes" && (
        <div>
          <input
            type="text" placeholder="Buscar rotas..."
            value={searchRoutes} onChange={e => setSearchRoutes(e.target.value)}
            style={{
              width: "100%", padding: "10px 14px", marginBottom: 20,
              background: "#0d1220", border: "1px solid #151d2e", borderRadius: 8,
              color: "#c4cede", fontFamily: "inherit", fontSize: 12, outline: "none",
            }}
          />
          {routeSections.map(section => (
            <div key={section} style={{ marginBottom: 22 }}>
              <div style={{
                fontSize: 10, color: "#3b5998", fontWeight: 700, marginBottom: 10,
                textTransform: "uppercase", letterSpacing: ".08em",
              }}>
                {section}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {filteredRoutes.filter(r => r.section === section).map((r, i) => {
                  const key = `${r.method}-${r.path}`;
                  const isOpen = expandedRoute === key;
                  return (
                    <div key={i}>
                      <div
                        onClick={() => setExpandedRoute(isOpen ? null : key)}
                        style={{
                          display: "flex", alignItems: "center", gap: 10,
                          background: isOpen ? "#111b30" : "#0d1220",
                          border: `1px solid ${isOpen ? "#1e2d45" : "#151d2e"}`,
                          borderRadius: isOpen ? "8px 8px 0 0" : 8,
                          padding: "10px 14px", cursor: "pointer", transition: "all .15s",
                        }}
                      >
                        <span style={{
                          fontWeight: 700, fontSize: 10, minWidth: 52, textAlign: "center",
                          padding: "3px 0", borderRadius: 4,
                          color: methodColor(r.method), background: `${methodColor(r.method)}12`,
                        }}>{r.method}</span>
                        <code style={{ flex: 1, fontSize: 12.5, color: "#c4cede", fontWeight: 500 }}>{r.path}</code>
                        <div style={{ display: "flex", gap: 4 }}>
                          {r.auth && <Badge color="#f59e0b">auth</Badge>}
                          {r.admin && <Badge color="#ef4444">admin</Badge>}
                        </div>
                        <span style={{ color: "#2a3a56", fontSize: 14, transform: isOpen ? "rotate(90deg)" : "none", transition: "transform .15s" }}>▸</span>
                      </div>
                      {isOpen && (
                        <div style={{
                          background: "#0c1424", border: "1px solid #1e2d45", borderTop: "none",
                          borderRadius: "0 0 8px 8px", padding: "14px 16px",
                        }}>
                          <div style={{ fontSize: 12, color: "#7a8caa", marginBottom: r.body ? 12 : 0, lineHeight: 1.5 }}>
                            {r.desc}
                          </div>
                          {r.body && (
                            <div>
                              <div style={{ fontSize: 10, color: "#3a4a66", fontWeight: 700, marginBottom: 6, textTransform: "uppercase" }}>Request body</div>
                              <pre style={{
                                background: "#080c18", borderRadius: 6, padding: "10px 12px",
                                fontSize: 11.5, color: "#6d8cff", overflowX: "auto",
                                border: "1px solid #111827",
                              }}>{r.body}</pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* EXTERNAL APIs */}
      {tab === "external" && (
        <div>
          <div style={{ fontSize: 11, color: "#3b5998", fontWeight: 700, marginBottom: 14, textTransform: "uppercase", letterSpacing: ".08em" }}>
            Endpoints Casa dos Dados
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 28 }}>
            {EXTERNAL_ENDPOINTS.map((e, i) => (
              <div key={i} style={{
                background: "#0d1220", border: "1px solid #151d2e", borderRadius: 10, padding: "14px 16px",
              }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#c4cede", marginBottom: 4 }}>{e.name}</div>
                <code style={{ fontSize: 11, color: "#4a7aff", display: "block", marginBottom: 6, wordBreak: "break-all" }}>{e.url}</code>
                <div style={{ fontSize: 11.5, color: "#4a5a76" }}>{e.desc}</div>
              </div>
            ))}
          </div>

          <div style={{
            background: "#0f1628", border: "1px solid #1a2540", borderRadius: 12, padding: 20,
          }}>
            <div style={{ fontSize: 11, color: "#3b5998", fontWeight: 700, marginBottom: 14, textTransform: "uppercase", letterSpacing: ".08em" }}>
              Fluxo de Captação
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
              {[
                { step: "1", label: "Prévia", desc: "POST /api/previa → pesquisa CNPJs com filtros (máx 10)", color: "#3b82f6" },
                { step: "2", label: "Gerar arquivo", desc: "POST /api/captar → solicita CSV na Casa dos Dados → retorna UUID", color: "#8b5cf6" },
                { step: "3", label: "Aguardar", desc: "GET /api/solicitacoes → lista e verifica status (processando → pronto)", color: "#f59e0b" },
                { step: "4", label: "Download", desc: "GET /api/baixar-solicitacao/:uuid → baixa ZIP/CSV quando pronto", color: "#22c55e" },
              ].map((s, i) => (
                <div key={s.step} style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 32 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: "50%",
                      background: `${s.color}18`, border: `2px solid ${s.color}50`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 12, fontWeight: 700, color: s.color,
                    }}>{s.step}</div>
                    {i < 3 && <div style={{ width: 2, height: 28, background: "#1a2540" }} />}
                  </div>
                  <div style={{ paddingBottom: 14 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: "#c4cede", marginBottom: 2 }}>{s.label}</div>
                    <div style={{ fontSize: 11.5, color: "#4a5a76", lineHeight: 1.5 }}>{s.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{
            marginTop: 16, background: "#0c1424", border: "1px solid #1a253a", borderRadius: 10,
            padding: "14px 16px", fontSize: 12, color: "#4a5a76", lineHeight: 1.6,
          }}>
            <b style={{ color: "#f59e0b" }}>Autenticação:</b> Todas as chamadas usam header <code style={{ color: "#8aabff" }}>api-key</code> salva na tabela config.
          </div>
        </div>
      )}

      {/* FILTERS */}
      {tab === "filters" && (
        <div>
          <div style={{ fontSize: 11, color: "#3b5998", fontWeight: 700, marginBottom: 14, textTransform: "uppercase", letterSpacing: ".08em" }}>
            Parâmetros de pesquisa — montar_pesquisa()
          </div>
          <div style={{
            background: "#0d1220", border: "1px solid #151d2e", borderRadius: 12, padding: 20,
          }}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1a2540" }}>
                    {["Parâmetro", "Descrição", "Exemplo"].map(h => (
                      <th key={h} style={{
                        textAlign: "left", padding: "8px 10px", color: "#3a4a66",
                        fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".06em",
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {PESQUISA_PARAMS.map(p => (
                    <tr key={p.param} style={{ borderBottom: "1px solid #111827" }}>
                      <td style={{ padding: "8px 10px" }}>
                        <code style={{ color: "#6d8cff", fontWeight: 600 }}>{p.param}</code>
                      </td>
                      <td style={{ padding: "8px 10px", color: "#7a8caa" }}>{p.desc}</td>
                      <td style={{ padding: "8px 10px" }}>
                        <code style={{ color: "#4a5a76", fontSize: 11 }}>{p.exemplo}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div style={{
            marginTop: 16, background: "#0f1628", border: "1px solid #1a2540", borderRadius: 12, padding: 20,
          }}>
            <div style={{ fontSize: 11, color: "#3b5998", fontWeight: 700, marginBottom: 12, textTransform: "uppercase", letterSpacing: ".08em" }}>
              Exemplo de payload enviado à API
            </div>
            <pre style={{
              background: "#080c18", borderRadius: 8, padding: 16,
              fontSize: 11.5, color: "#7a8caa", overflowX: "auto", lineHeight: 1.7,
              border: "1px solid #111827",
            }}>{JSON.stringify({
              codigo_atividade_principal: ["6920601"],
              situacao_cadastral: ["ATIVA"],
              uf: ["sp", "rj"],
              municipio: ["sao paulo"],
              mais_filtros: { com_telefone: true, com_email: true },
            }, null, 2)}</pre>
          </div>

          <div style={{
            marginTop: 16, background: "#0c1424", border: "1px solid #1a253a", borderRadius: 10,
            padding: "14px 16px", fontSize: 12, color: "#4a5a76", lineHeight: 1.6,
          }}>
            <b style={{ color: "#22c55e" }}>Dica:</b> UFs e municípios são enviados em minúsculo. CNAEs são strings. O campo <code style={{ color: "#8aabff" }}>limite</code> aceita 1 a 1000.
          </div>
        </div>
      )}
    </div>
  );
}
