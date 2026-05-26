import { useState } from "react";

const steps = [
  {
    num: 1,
    title: "Baixe o ZIP",
    icon: "📦",
    color: "#6d8cff",
    content: `Baixe o arquivo **prospecta_deploy.zip** que foi gerado acima. Extraia os 6 arquivos em uma pasta no seu computador.`,
    files: ["app.py", "db.py", "requirements.txt", "render.yaml", ".gitignore", "README.md"],
  },
  {
    num: 2,
    title: "Suba no GitHub",
    icon: "🐙",
    color: "#a78bfa",
    content: `Acesse **github.com** e faça login (ou crie uma conta).`,
    substeps: [
      'Clique no **+** (canto superior direito) → **New repository**',
      'Nome: **captador-cnpj** → marque **Public** → **Create repository**',
      'Na página seguinte, clique em **"uploading an existing file"**',
      'Arraste os **6 arquivos** extraídos do ZIP para a área do navegador',
      'Clique no botão verde **Commit changes**',
    ],
    tip: "Se já tem o repo, basta atualizar os arquivos: abra cada um → Edit (lápis) → cole o conteúdo novo → Commit.",
  },
  {
    num: 3,
    title: "Crie o serviço no Render",
    icon: "☁️",
    color: "#22c55e",
    content: `Acesse **render.com** e faça login com o GitHub.`,
    substeps: [
      'Clique em **New +** (botão azul, topo) → **Blueprint**',
      'Selecione o repositório **captador-cnpj** → **Connect**',
      'O Render detecta o render.yaml e mostra: **1 Web Service** + **1 PostgreSQL Database**',
      'Ele vai pedir o valor de **ADMIN_SENHA** — digite uma senha forte e anote!',
      'Clique em **Apply** (ou **Create Resources**)',
      'Aguarde o build (~2-3 minutos). Quando ficar **"Live"**, seu site está no ar!',
    ],
    tip: "O render.yaml já inclui Postgres gratuito. Seus dados NUNCA se perdem, mesmo quando o Render hiberna.",
  },
  {
    num: 4,
    title: "Primeiro acesso",
    icon: "🔑",
    color: "#f59e0b",
    content: `Abra a URL gerada pelo Render (ex: captador-cnpj.onrender.com).`,
    substeps: [
      'Login: **admin** / a senha que você definiu no passo anterior',
      'Vá em **Configurações** → cole sua **API KEY** da Casa dos Dados → **Salvar**',
      'Clique em **Testar conexão** para verificar',
      'Pronto! Pode captar CNPJs e os leads ficam salvos permanentemente',
    ],
  },
  {
    num: 5,
    title: "Use os Leads Salvos",
    icon: "💾",
    color: "#f472b6",
    content: `Agora seus dados ficam salvos! Veja como usar:`,
    substeps: [
      '**Captação** → faça uma prévia → clique em **"Salvar no banco"** → leads ficam guardados',
      '**Leads Salvos** → importe qualquer CSV que você já tenha',
      '**Busca avançada** → filtre por UF, município, CNAE, com email/telefone',
      '**Exportar CSV** → baixe os leads filtrados sem gastar créditos da API',
    ],
    tip: "Você pode importar CSVs antigos que já baixou antes. Tudo fica centralizado no banco.",
  },
];

export default function DeployGuide() {
  const [activeStep, setActiveStep] = useState(0);
  const [doneSteps, setDoneSteps] = useState(new Set());

  const toggleDone = (i) => {
    const next = new Set(doneSteps);
    if (next.has(i)) next.delete(i); else next.add(i);
    setDoneSteps(next);
  };

  const step = steps[activeStep];
  const progress = (doneSteps.size / steps.length) * 100;

  return (
    <div style={{
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      background: "#080c15", color: "#c4cede", minHeight: "100vh",
      maxWidth: 800, margin: "0 auto", padding: "24px 16px",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
      `}</style>

      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: "#e8ecf4", marginBottom: 4 }}>
          Deploy <span style={{ color: "#6d8cff" }}>Prospecta+</span>
        </div>
        <p style={{ fontSize: 12, color: "#445570" }}>
          Siga os {steps.length} passos para colocar no ar com banco persistente
        </p>
        {/* Progress */}
        <div style={{
          marginTop: 14, height: 6, background: "#111827", borderRadius: 3, overflow: "hidden",
        }}>
          <div style={{
            height: "100%", width: `${progress}%`, background: "linear-gradient(90deg, #6d8cff, #22c55e)",
            borderRadius: 3, transition: "width .4s ease",
          }} />
        </div>
        <div style={{ fontSize: 11, color: "#334155", marginTop: 4 }}>
          {doneSteps.size}/{steps.length} concluídos
        </div>
      </div>

      {/* Step selector */}
      <div style={{ display: "flex", gap: 6, marginBottom: 24, flexWrap: "wrap" }}>
        {steps.map((s, i) => (
          <button key={i} onClick={() => setActiveStep(i)} style={{
            flex: 1, minWidth: 80, padding: "12px 6px", border: "none",
            borderRadius: 10,
            background: activeStep === i ? "#111b30" : "#0b1020",
            cursor: "pointer", transition: "all .2s",
            boxShadow: activeStep === i ? `0 0 0 1.5px ${s.color}40` : "none",
            position: "relative",
          }}>
            <div style={{ fontSize: 20, marginBottom: 4 }}>
              {doneSteps.has(i) ? "✅" : s.icon}
            </div>
            <div style={{
              fontSize: 10, fontWeight: 600, color: activeStep === i ? s.color : "#3a4a66",
              fontFamily: "inherit",
            }}>{s.title}</div>
          </button>
        ))}
      </div>

      {/* Active step detail */}
      <div style={{
        background: "#0d1424", border: `1px solid ${step.color}25`,
        borderRadius: 14, padding: 24, marginBottom: 16,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: `${step.color}12`, border: `2px solid ${step.color}35`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 22,
          }}>{step.icon}</div>
          <div>
            <div style={{ fontSize: 10, color: step.color, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em" }}>
              Passo {step.num}
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, color: "#e8ecf4" }}>{step.title}</div>
          </div>
        </div>

        <div style={{
          fontSize: 13, color: "#8a9ab6", lineHeight: 1.7, marginBottom: 16,
        }} dangerouslySetInnerHTML={{
          __html: step.content.replace(/\*\*(.*?)\*\*/g, '<b style="color:#e8ecf4">$1</b>')
        }} />

        {step.files && (
          <div style={{
            background: "#080c18", borderRadius: 8, padding: 14,
            marginBottom: 16, border: "1px solid #151d2e",
          }}>
            <div style={{ fontSize: 10, color: "#3a4a66", fontWeight: 700, marginBottom: 8, textTransform: "uppercase" }}>
              Arquivos do ZIP
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {step.files.map(f => (
                <span key={f} style={{
                  padding: "4px 12px", borderRadius: 6,
                  background: "#111827", color: "#6d8cff",
                  fontSize: 12, fontWeight: 500,
                }}>{f}</span>
              ))}
            </div>
          </div>
        )}

        {step.substeps && (
          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {step.substeps.map((ss, i) => (
              <div key={i} style={{
                display: "flex", gap: 12, alignItems: "flex-start",
              }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 28 }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: "50%",
                    background: `${step.color}15`, border: `1.5px solid ${step.color}40`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, fontWeight: 700, color: step.color, flexShrink: 0,
                  }}>{i + 1}</div>
                  {i < step.substeps.length - 1 && (
                    <div style={{ width: 1.5, height: 20, background: "#1a2540" }} />
                  )}
                </div>
                <div style={{
                  fontSize: 12.5, color: "#8a9ab6", lineHeight: 1.6, paddingBottom: 8,
                }} dangerouslySetInnerHTML={{
                  __html: ss.replace(/\*\*(.*?)\*\*/g, '<b style="color:#e8ecf4">$1</b>')
                }} />
              </div>
            ))}
          </div>
        )}

        {step.tip && (
          <div style={{
            marginTop: 14, padding: "10px 14px", borderRadius: 8,
            background: "#0c1e2a", border: "1px solid #1a3a4a",
            fontSize: 12, color: "#60a5fa", lineHeight: 1.5,
          }}>
            💡 {step.tip}
          </div>
        )}

        <button onClick={() => toggleDone(activeStep)} style={{
          marginTop: 18, padding: "10px 20px", border: "none", borderRadius: 8,
          background: doneSteps.has(activeStep) ? "#14532d" : `${step.color}20`,
          color: doneSteps.has(activeStep) ? "#4ade80" : step.color,
          fontFamily: "inherit", fontSize: 13, fontWeight: 600,
          cursor: "pointer", transition: "all .2s",
        }}>
          {doneSteps.has(activeStep) ? "✓ Concluído" : "Marcar como concluído"}
        </button>
      </div>

      {/* Nav buttons */}
      <div style={{ display: "flex", gap: 10, justifyContent: "space-between" }}>
        <button disabled={activeStep === 0} onClick={() => setActiveStep(activeStep - 1)} style={{
          padding: "10px 20px", border: "1px solid #1e2d45", borderRadius: 8,
          background: "#0b1020", color: activeStep === 0 ? "#1e2d45" : "#8a9ab6",
          fontFamily: "inherit", fontSize: 12, fontWeight: 600,
          cursor: activeStep === 0 ? "default" : "pointer",
        }}>← Anterior</button>
        <button disabled={activeStep === steps.length - 1} onClick={() => setActiveStep(activeStep + 1)} style={{
          padding: "10px 20px", border: "none", borderRadius: 8,
          background: activeStep === steps.length - 1 ? "#111827" : "#6d8cff",
          color: activeStep === steps.length - 1 ? "#334155" : "#fff",
          fontFamily: "inherit", fontSize: 12, fontWeight: 600,
          cursor: activeStep === steps.length - 1 ? "default" : "pointer",
        }}>Próximo →</button>
      </div>

      {/* Quick links */}
      <div style={{
        marginTop: 24, padding: 18, background: "#0b1020",
        borderRadius: 12, border: "1px solid #151d2e",
      }}>
        <div style={{ fontSize: 10, color: "#3a4a66", fontWeight: 700, marginBottom: 10, textTransform: "uppercase", letterSpacing: ".08em" }}>
          Links rápidos
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {[
            { label: "GitHub", url: "https://github.com/new", color: "#a78bfa" },
            { label: "Render", url: "https://dashboard.render.com/select-repo?type=blueprint", color: "#22c55e" },
            { label: "Casa dos Dados", url: "https://casadosdados.com.br", color: "#f59e0b" },
          ].map(l => (
            <a key={l.label} href={l.url} target="_blank" rel="noopener" style={{
              padding: "8px 16px", borderRadius: 8, textDecoration: "none",
              background: `${l.color}12`, border: `1px solid ${l.color}30`,
              color: l.color, fontSize: 12, fontWeight: 600,
              fontFamily: "inherit",
            }}>{l.label} ↗</a>
          ))}
        </div>
      </div>
    </div>
  );
}
