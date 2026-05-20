"""
Captador de CNPJs — Casa dos Dados
app.py — versão completa corrigida
"""

import io
import os
import json
import secrets
import datetime
from functools import wraps

import requests
from flask import (
    Flask, jsonify, request,
    send_file, Response, session, redirect,
)

from db import (
    init_db, autenticar, listar_usuarios,
    criar_usuario, remover_usuario, alterar_senha,
    get_api_key, set_api_key,
)

# =========================================================
# APP
# =========================================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

init_db()

ENDPOINT_GERAR     = "https://api.casadosdados.com.br/v5/cnpj/pesquisa/arquivo"
ENDPOINT_CONSULTAR = "https://api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo"
ENDPOINT_LISTAR    = "https://api.casadosdados.com.br/v4/cnpj/pesquisa/arquivo"
ENDPOINT_PESQUISA  = "https://api.casadosdados.com.br/v5/cnpj/pesquisa"
ENDPOINT_SALDO     = "https://api.casadosdados.com.br/v5/saldo"

_LOGS = []

def add_log(level, origem, msg, detalhe=""):
    _LOGS.append({
        "ts":      datetime.datetime.now().strftime("%d/%m %H:%M:%S"),
        "level":   level,
        "origem":  origem,
        "msg":     msg,
        "detalhe": str(detalhe)[:500],
    })
    if len(_LOGS) > 200:
        _LOGS.pop(0)

# =========================================================
# DECORATORS
# =========================================================

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("uid"):
            return jsonify({"ok": False, "msg": "Faça login."}), 401
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("is_admin"):
            return jsonify({"ok": False, "msg": "Acesso restrito ao admin."}), 403
        return f(*a, **k)
    return w

def _h(key):
    return {"api-key": key, "Content-Type": "application/json"}

# =========================================================
# PESQUISA BUILDER
# =========================================================

def montar_pesquisa(d):
    p = {
        "codigo_atividade_principal": [
            c.strip() for c in d.get("cnae", "").split(",") if c.strip()
        ],
        "situacao_cadastral": [d.get("situacao") or "ATIVA"],
    }
    if d.get("ufs"):
        p["uf"] = [u.strip().lower() for u in d["ufs"].split(",") if u.strip()]
    if d.get("municipios"):
        p["municipio"] = [m.strip().lower() for m in d["municipios"].split(",") if m.strip()]
    if d.get("ultimos_dias"):
        try:
            dias = int(d["ultimos_dias"])
            if dias > 0:
                p["data_abertura"] = {"ultimos_dias": dias}
        except Exception:
            pass
    if d.get("somente_mei"):
        p["mei"] = {"optante": True}
    mais = {}
    if d.get("com_telefone"):
        mais["com_telefone"] = True
    if d.get("com_email"):
        mais["com_email"] = True
    if mais:
        p["mais_filtros"] = mais
    try:
        lim = int(d.get("total_linhas", 0) or 0)
        if 1 <= lim <= 1000:
            p["limite"] = lim
    except Exception:
        pass
    return p

# =========================================================
# HTML LOGIN
# =========================================================

HTML_LOGIN = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login — Captador CNPJ</title>
<link rel="icon" href="data:,">
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{background:#080e1a;color:#e2e8f0;font-family:'DM Sans',sans-serif;
     display:flex;justify-content:center;align-items:center;min-height:100vh}
.card{background:#0f1829;border:1px solid #1e2d45;border-radius:18px;padding:44px 40px;width:380px}
h2{font-size:22px;font-weight:600;margin-bottom:6px;color:#f1f5f9}
.sub{font-size:13px;color:#64748b;margin-bottom:32px}
label{font-size:12px;color:#64748b;display:block;margin-bottom:5px;font-weight:500}
.field{margin-bottom:18px}
input{width:100%;padding:11px 14px;background:#080e1a;border:1px solid #1e2d45;
      border-radius:10px;color:#f1f5f9;font-size:14px;outline:none;transition:.2s;font-family:inherit}
input:focus{border-color:#4f6ef7;box-shadow:0 0 0 3px rgba(79,110,247,.15)}
.btn{width:100%;padding:13px;background:#4f6ef7;border:none;border-radius:10px;
     color:#fff;font-weight:600;font-size:15px;cursor:pointer;font-family:inherit;transition:.2s}
.btn:hover{background:#3d5ce6}
.erro{margin-top:14px;font-size:13px;color:#f87171;min-height:18px;text-align:center}
</style>
</head>
<body>
<div class="card">
  <h2>Captador CNPJ</h2>
  <p class="sub">Acesse sua conta para continuar</p>
  <div class="field"><label>Usuário</label>
    <input id="u" type="text" placeholder="admin" autocomplete="username">
  </div>
  <div class="field"><label>Senha</label>
    <input id="s" type="password" placeholder="••••••••" autocomplete="current-password">
  </div>
  <button class="btn" onclick="entrar()">Entrar</button>
  <div class="erro" id="erro"></div>
</div>
<script>
async function entrar(){
  document.getElementById('erro').textContent='';
  const r=await fetch('/api/login',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('u').value,
                         senha:document.getElementById('s').value})});
  const d=await r.json();
  if(d.ok) location.reload();
  else document.getElementById('erro').textContent=d.msg;
}
document.addEventListener('keydown',e=>{if(e.key==='Enter')entrar()});
</script>
</body>
</html>"""

# =========================================================
# HTML APP
# =========================================================

HTML_APP = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Captador CNPJ</title>
<link rel="icon" href="data:,">
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{background:#080e1a;color:#e2e8f0;font-family:'DM Sans',sans-serif;display:flex;min-height:100vh}

.sidebar{width:230px;min-width:230px;background:#0f1829;border-right:1px solid #1e2d45;
  display:flex;flex-direction:column;position:fixed;top:0;left:0;height:100vh;overflow-y:auto}
.logo{padding:22px 20px 20px;border-bottom:1px solid #1e2d45}
.logo h1{font-size:15px;font-weight:600;color:#f1f5f9}
.logo .badge{font-size:11px;color:#4f6ef7;background:#0d1e3d;padding:2px 8px;
  border-radius:20px;display:inline-block;margin-top:4px}
.nav{padding:12px 10px;flex:1}
.nav-section{font-size:10px;font-weight:600;color:#334155;letter-spacing:.08em;
  text-transform:uppercase;padding:14px 10px 6px}
.nav-btn{display:flex;align-items:center;gap:10px;width:100%;padding:9px 12px;
  border:none;background:none;color:#64748b;font-size:13.5px;font-family:inherit;
  border-radius:8px;cursor:pointer;text-align:left;transition:.15s;font-weight:500}
.nav-btn:hover{background:#1e2d45;color:#e2e8f0}
.nav-btn.active{background:#1a2547;color:#7c9ef8}
.nav-btn svg{width:16px;height:16px;flex-shrink:0}

.saldo-box{padding:14px 16px;margin:10px;background:#080e1a;border:1px solid #1e2d45;border-radius:10px}
.saldo-box .s-label{font-size:11px;color:#475569;margin-bottom:4px;font-weight:600;
  text-transform:uppercase;letter-spacing:.05em}
.saldo-box .s-val{color:#7c9ef8;font-weight:700;font-size:22px;line-height:1}
.saldo-box .s-unit{font-size:11px;color:#475569;margin-top:2px}
.btn-atualizar{width:100%;margin-top:10px;padding:8px;background:#1e2d45;border:none;
  border-radius:8px;color:#94a3b8;font-size:12px;font-family:inherit;cursor:pointer;transition:.15s}
.btn-atualizar:hover{background:#253550;color:#e2e8f0}

.user-box{padding:14px 16px;border-top:1px solid #1e2d45;display:flex;align-items:center;gap:10px}
.user-av{width:30px;height:30px;border-radius:50%;background:#1a2547;display:flex;
  align-items:center;justify-content:center;font-size:12px;font-weight:600;color:#7c9ef8;flex-shrink:0}
.user-name{font-size:13px;font-weight:500;color:#cbd5e1;flex:1}
.btn-logout{background:none;border:none;cursor:pointer;color:#475569;font-size:11px;
  padding:4px 8px;border-radius:6px;font-family:inherit;transition:.15s}
.btn-logout:hover{color:#f87171;background:#1e2d45}

.main{margin-left:230px;flex:1;padding:28px 32px;min-height:100vh}
.page{display:none}
.page.active{display:block}
.page-title{font-size:20px;font-weight:600;color:#f1f5f9;margin-bottom:4px}
.page-sub{font-size:13px;color:#475569;margin-bottom:24px}

.card{background:#0f1829;border:1px solid #1e2d45;border-radius:14px;padding:24px;margin-bottom:20px}
.card-title{font-size:11px;font-weight:600;color:#475569;margin-bottom:16px;
  text-transform:uppercase;letter-spacing:.07em}

label.lbl{font-size:12px;color:#475569;font-weight:500;display:block;margin-bottom:4px}
input.inp,select.inp{width:100%;padding:10px 13px;background:#080e1a;border:1px solid #1e2d45;
  border-radius:9px;color:#e2e8f0;font-size:13.5px;font-family:inherit;outline:none;transition:.2s}
input.inp:focus,select.inp:focus{border-color:#4f6ef7;box-shadow:0 0 0 3px rgba(79,110,247,.1)}
select.inp option{background:#0f1829}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
.field{margin-bottom:14px}
.checks{display:flex;gap:20px;flex-wrap:wrap;margin:4px 0 16px}
.checks label{display:flex;align-items:center;gap:7px;font-size:13px;color:#94a3b8;cursor:pointer}
.checks input[type=checkbox]{width:15px;height:15px;accent-color:#4f6ef7}

.btn{padding:10px 20px;border:none;border-radius:9px;font-family:inherit;font-weight:600;
  font-size:13.5px;cursor:pointer;transition:.2s;display:inline-flex;align-items:center;gap:7px}
.btn-primary{background:#4f6ef7;color:#fff}
.btn-primary:hover{background:#3d5ce6}
.btn-secondary{background:#1e2d45;color:#94a3b8}
.btn-secondary:hover{background:#253550;color:#e2e8f0}
.btn-danger{background:#3d1515;color:#f87171;border:1px solid #5a1f1f}
.btn-danger:hover{background:#5a1f1f}
.btn-sm{padding:6px 12px;font-size:12px}
.btn-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}

.tbl-wrap{overflow-x:auto;margin-top:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#0d1626;color:#475569;padding:10px 12px;text-align:left;font-weight:600;
   font-size:11px;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #1e2d45}
td{padding:10px 12px;border-bottom:1px solid #0f1829;color:#cbd5e1;vertical-align:middle}
tr:hover td{background:#0d1626}

.badge{display:inline-block;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600}
.badge-green{background:#052e16;color:#4ade80;border:1px solid #14532d}
.badge-amber{background:#2d1a02;color:#fbbf24;border:1px solid #78350f}
.badge-red{background:#1f0606;color:#f87171;border:1px solid #7f1d1d}
.badge-blue{background:#0c1e40;color:#60a5fa;border:1px solid #1e3a5f}
.badge-gray{background:#1a2130;color:#64748b;border:1px solid #334155}

.alert{padding:12px 16px;border-radius:9px;font-size:13px;margin-bottom:14px;
  display:flex;align-items:flex-start;gap:10px;line-height:1.5}
.alert-info{background:#0c1e40;border:1px solid #1e3a5f;color:#93c5fd}
.alert-warn{background:#2d1a02;border:1px solid #78350f;color:#fcd34d}
.alert-error{background:#1f0606;border:1px solid #7f1d1d;color:#fca5a5}
.alert-ok{background:#052e16;border:1px solid #14532d;color:#86efac}

.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:20px}
.stat-card{background:#0f1829;border:1px solid #1e2d45;border-radius:12px;padding:18px 20px}
.stat-label{font-size:11px;color:#475569;font-weight:600;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:6px}
.stat-val{font-size:24px;font-weight:600;color:#f1f5f9}
.stat-val.green{color:#4ade80}
.stat-val.amber{color:#fbbf24}
.stat-val.red{color:#f87171}
.stat-val.blue{color:#60a5fa}

.log-panel{background:#050c18;border:1px solid #1e2d45;border-radius:10px;
  font-family:'DM Mono',monospace,'Courier New';font-size:12px;
  max-height:380px;overflow-y:auto}
.log-row{display:flex;gap:0;padding:7px 14px;border-bottom:1px solid #0a1120;align-items:flex-start}
.log-row:last-child{border-bottom:none}
.log-row:hover{background:#0a1525}
.log-ts{color:#334155;min-width:108px;flex-shrink:0}
.log-lv{min-width:54px;flex-shrink:0;font-weight:700}
.log-lv.INFO{color:#38bdf8}
.log-lv.WARN{color:#fbbf24}
.log-lv.ERROR{color:#f87171}
.log-orig{color:#4f6ef7;min-width:120px;flex-shrink:0}
.log-msg{color:#94a3b8;flex:1}
.log-det{color:#334155;font-size:11px;margin-top:2px;word-break:break-all}
.log-empty{padding:24px;text-align:center;color:#334155}
.log-filters{display:flex;gap:8px;flex-wrap:wrap}
.lf-btn{padding:5px 13px;border-radius:20px;border:1px solid #1e2d45;background:none;
  color:#475569;font-size:12px;cursor:pointer;font-family:inherit;transition:.15s}
.lf-btn:hover{border-color:#4f6ef7;color:#7c9ef8}
.lf-btn.on{background:#0d1e3d;border-color:#4f6ef7;color:#7c9ef8}

.dl-link{color:#60a5fa;text-decoration:none;font-weight:600;font-size:12px}
.dl-link:hover{text-decoration:underline}
.api-row{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap}
.api-row .inp{flex:1;min-width:200px}
</style>
</head>
<body>

<div class="sidebar">
  <div class="logo">
    <h1>Captador <span style="color:#4f6ef7">CNPJ</span></h1>
    <span class="badge">Casa dos Dados</span>
  </div>

  <div class="nav">
    <div class="nav-section">Principal</div>
    <button class="nav-btn active" onclick="goto('captacao')" id="nb-captacao">
      <svg fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"/><path stroke-linecap="round" d="m21 21-4.35-4.35"/>
      </svg> Captação
    </button>
    <button class="nav-btn" onclick="goto('solicitacoes')" id="nb-solicitacoes">
      <svg fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 4H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/>
      </svg> Solicitações
    </button>

    <div class="nav-section" id="admin-section" style="display:none">Admin</div>
    <button class="nav-btn" onclick="goto('usuarios')" id="nb-usuarios" style="display:none">
      <svg fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-1a4 4 0 0 0-5.33-3.77M9 20H4v-1a4 4 0 0 1 5.33-3.77M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"/>
      </svg> Usuários
    </button>
    <button class="nav-btn" onclick="goto('configuracoes')" id="nb-configuracoes" style="display:none">
      <svg fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/>
        <path stroke-linecap="round" stroke-linejoin="round" d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg> Configurações
    </button>
    <button class="nav-btn" onclick="goto('logs')" id="nb-logs" style="display:none">
      <svg fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h16M4 14h10M4 18h6"/>
      </svg> Logs & Erros
    </button>
  </div>

  <div class="saldo-box">
    <div class="s-label">Saldo API</div>
    <div class="s-val" id="saldo-val">—</div>
    <div class="s-unit">créditos disponíveis</div>
    <button class="btn-atualizar" onclick="carregarSaldo()">↻ Atualizar</button>
  </div>

  <div class="user-box">
    <div class="user-av" id="user-av">A</div>
    <span class="user-name" id="user-name">—</span>
    <button class="btn-logout" onclick="logout()">Sair</button>
  </div>
</div>

<div class="main">

  <!-- CAPTAÇÃO -->
  <div class="page active" id="page-captacao">
    <div class="page-title">Captação de CNPJs</div>
    <div class="page-sub">Configure os filtros e gere o arquivo CSV</div>
    <div class="card">
      <div class="card-title">Filtros de busca</div>
      <div class="grid2">
        <div class="field"><label class="lbl">CNAE(s) — separar por vírgula</label>
          <input class="inp" id="cnae" value="6920601"></div>
        <div class="field"><label class="lbl">Situação Cadastral</label>
          <select class="inp" id="situacao">
            <option value="ATIVA">Ativa</option>
            <option value="BAIXADA">Baixada</option>
            <option value="INAPTA">Inapta</option>
            <option value="SUSPENSA">Suspensa</option>
          </select></div>
        <div class="field"><label class="lbl">UF(s) — ex: SP,RJ</label>
          <input class="inp" id="ufs" placeholder="Todas"></div>
        <div class="field"><label class="lbl">Município(s)</label>
          <input class="inp" id="municipios" placeholder="Todos"></div>
        <div class="field"><label class="lbl">Últimos N dias (abertura)</label>
          <input class="inp" id="ultimos_dias" type="number" placeholder="0 = ignorar"></div>
        <div class="field"><label class="lbl">Total de linhas (0 = máximo)</label>
          <input class="inp" id="total_linhas" type="number" placeholder="0"></div>
      </div>
      <div class="field"><label class="lbl">Nome do arquivo</label>
        <input class="inp" id="nome" value="captacao" style="max-width:300px"></div>
      <div class="checks">
        <label><input type="checkbox" id="somente_mei"> Somente MEI</label>
        <label><input type="checkbox" id="com_telefone"> Com telefone</label>
        <label><input type="checkbox" id="com_email"> Com e-mail</label>
      </div>
      <div class="btn-row">
        <button class="btn btn-secondary" onclick="previa()">
          <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8"/><path stroke-linecap="round" d="m21 21-4.35-4.35"/>
          </svg> Prévia
        </button>
        <button class="btn btn-primary" onclick="captar()">
          <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2M7 10l5 5 5-5M12 4v11"/>
          </svg> Gerar Arquivo
        </button>
      </div>
    </div>
    <div id="alert-captacao"></div>
    <div id="preview-card" class="card" style="display:none">
      <div class="card-title">Prévia — primeiros registros</div>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>CNPJ</th><th>Razão Social</th><th>Município</th><th>UF</th><th>Telefone</th><th>E-mail</th></tr></thead>
          <tbody id="preview-body"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- SOLICITAÇÕES -->
  <div class="page" id="page-solicitacoes">
    <div class="page-title">Minhas Solicitações</div>
    <div class="page-sub">Arquivos gerados — aguarde o processamento e baixe o CSV</div>
    <div style="display:flex;gap:10px;margin-bottom:20px">
      <button class="btn btn-primary" onclick="listarSolicitacoes()">
        <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582M20 20v-5h-.581M5.634 9A9 9 0 0 1 20 15M18.366 15A9 9 0 0 1 4 9"/>
        </svg> Atualizar lista
      </button>
    </div>
    <div id="alert-sol"></div>
    <div class="card">
      <div id="sol-body" style="text-align:center;color:#334155;padding:30px 0">
        Clique em "Atualizar lista" para carregar as solicitações.
      </div>
    </div>
  </div>

  <!-- USUÁRIOS -->
  <div class="page" id="page-usuarios">
    <div class="page-title">Gerenciar Usuários</div>
    <div class="page-sub">Adicione ou remova acessos ao sistema</div>
    <div class="card">
      <div class="card-title">Novo usuário</div>
      <div class="grid3">
        <div class="field"><label class="lbl">Usuário</label>
          <input class="inp" id="nu-user" placeholder="nome_usuario"></div>
        <div class="field"><label class="lbl">Senha</label>
          <input class="inp" id="nu-senha" type="password" placeholder="••••••••"></div>
        <div class="field"><label class="lbl">Perfil</label>
          <select class="inp" id="nu-admin">
            <option value="0">Operador</option>
            <option value="1">Admin</option>
          </select></div>
      </div>
      <div id="alert-nu"></div>
      <button class="btn btn-primary" onclick="criarUsuario()">Criar usuário</button>
    </div>
    <div class="card">
      <div class="card-title">Usuários cadastrados</div>
      <div id="alert-user"></div>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>ID</th><th>Usuário</th><th>Perfil</th><th>Nova senha</th><th>Ações</th></tr></thead>
          <tbody id="user-body"><tr><td colspan="5" style="text-align:center;color:#334155">Carregando...</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- CONFIGURAÇÕES -->
  <div class="page" id="page-configuracoes">
    <div class="page-title">Configurações</div>
    <div class="page-sub">API KEY e diagnóstico de conexão</div>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-label">Status API</div><div class="stat-val" id="cfg-status-api">—</div></div>
      <div class="stat-card"><div class="stat-label">Saldo</div><div class="stat-val blue" id="cfg-saldo">—</div></div>
      <div class="stat-card"><div class="stat-label">API KEY</div><div class="stat-val" id="cfg-key-status">—</div></div>
    </div>
    <div class="card">
      <div class="card-title">API KEY — Casa dos Dados</div>
      <div id="alert-cfg"></div>
      <div class="api-row">
        <input class="inp" id="cfg-key-input" type="password" placeholder="Cole sua API KEY aqui">
        <button class="btn btn-primary" onclick="salvarKey()">Salvar</button>
        <button class="btn btn-secondary" onclick="verKey()">Ver KEY</button>
        <button class="btn btn-secondary" onclick="testarConexao()">Testar conexão</button>
      </div>
      <div id="cfg-key-msg" style="margin-top:10px;font-size:13px;color:#64748b"></div>
    </div>
    <div class="card">
      <div class="card-title">Diagnóstico rápido</div>
      <button class="btn btn-secondary" onclick="diagnostico()" style="margin-bottom:16px">Rodar diagnóstico</button>
      <div id="diag-body"></div>
    </div>
  </div>

  <!-- LOGS -->
  <div class="page" id="page-logs">
    <div class="page-title">Logs & Painel de Erros</div>
    <div class="page-sub">Rastreie todas as operações e identifique problemas facilmente</div>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-label">Total de logs</div><div class="stat-val" id="log-count">0</div></div>
      <div class="stat-card"><div class="stat-label">Erros</div><div class="stat-val red" id="log-errors">0</div></div>
      <div class="stat-card"><div class="stat-label">Avisos</div><div class="stat-val amber" id="log-warns">0</div></div>
      <div class="stat-card"><div class="stat-label">Info</div><div class="stat-val blue" id="log-infos">0</div></div>
    </div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <div class="log-filters">
          <button class="lf-btn on" id="f-ALL" onclick="setFiltro('ALL')">Todos</button>
          <button class="lf-btn" id="f-ERROR" onclick="setFiltro('ERROR')">Erros</button>
          <button class="lf-btn" id="f-WARN" onclick="setFiltro('WARN')">Avisos</button>
          <button class="lf-btn" id="f-INFO" onclick="setFiltro('INFO')">Info</button>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-secondary btn-sm" onclick="carregarLogs()">Atualizar</button>
          <button class="btn btn-danger btn-sm" onclick="limparLogs()">Limpar</button>
        </div>
      </div>
      <div class="log-panel" id="log-panel">
        <div class="log-empty">Nenhum log ainda.</div>
      </div>
    </div>
  </div>

</div>

<script>
let isAdmin = false;
let logFiltro = 'ALL';
let allLogs = [];

// ---- INIT ----
(async()=>{
  const r = await fetch('/api/eu');
  if(!r.ok){ location.reload(); return; }
  const d = await r.json();
  isAdmin = d.is_admin;
  document.getElementById('user-name').textContent = d.username;
  document.getElementById('user-av').textContent = d.username[0].toUpperCase();
  if(isAdmin){
    document.getElementById('admin-section').style.display='block';
    ['nb-usuarios','nb-configuracoes','nb-logs'].forEach(id=>{
      document.getElementById(id).style.display='flex';
    });
    carregarUsuarios();
    carregarCfgStats();
  }
  carregarSaldo();
})();

// ---- NAV ----
function goto(page){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('page-'+page).classList.add('active');
  document.getElementById('nb-'+page).classList.add('active');
  if(page==='solicitacoes') listarSolicitacoes();
  if(page==='logs') carregarLogs();
}

// ---- ALERTS ----
function showAlert(id,type,msg){
  const m={ok:'alert-ok',info:'alert-info',warn:'alert-warn',error:'alert-error'};
  document.getElementById(id).innerHTML=`<div class="alert ${m[type]||'alert-info'}">${msg}</div>`;
}
function clearAlert(id){ document.getElementById(id).innerHTML=''; }

// ---- LOGOUT ----
async function logout(){
  await fetch('/api/logout',{method:'POST'});
  location.reload();
}

// ---- SALDO — extrai só o número total ----
async function carregarSaldo(){
  const el = document.getElementById('saldo-val');
  el.textContent = '...';
  try {
    const r = await fetch('/api/saldo',{method:'POST'});
    const d = await r.json();
    if(d.ok && d.dados){
      const s = d.dados;
      // tenta extrair saldo_total, depois saldo, depois creditos
      const val = s.saldo_total ?? s.saldo ?? s.creditos ?? s.total ?? null;
      if(val !== null){
        el.textContent = Number(val).toLocaleString('pt-BR');
      } else {
        // fallback: mostra o primeiro número encontrado no objeto
        const nums = JSON.stringify(s).match(/\d+/);
        el.textContent = nums ? nums[0] : '—';
      }
    } else {
      el.textContent = '—';
    }
  } catch(e){
    el.textContent = '—';
  }
}

// ---- FILTROS ----
function filtros(){
  return {
    cnae:         document.getElementById('cnae').value,
    situacao:     document.getElementById('situacao').value,
    ufs:          document.getElementById('ufs').value,
    municipios:   document.getElementById('municipios').value,
    ultimos_dias: document.getElementById('ultimos_dias').value,
    total_linhas: document.getElementById('total_linhas').value,
    nome:         document.getElementById('nome').value || 'captacao',
    somente_mei:  document.getElementById('somente_mei').checked,
    com_telefone: document.getElementById('com_telefone').checked,
    com_email:    document.getElementById('com_email').checked,
  };
}

// ---- PRÉVIA ----
async function previa(){
  clearAlert('alert-captacao');
  document.getElementById('preview-card').style.display='none';
  showAlert('alert-captacao','info','Buscando prévia...');
  try {
    const r = await fetch('/api/previa',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(filtros())});
    const d = await r.json();
    if(!d.ok){ showAlert('alert-captacao','error','Erro: '+(d.msg||'Desconhecido')); return; }

    // a API retorna dados em vários formatos possíveis
    const raw = d.dados;
    let lista = [];
    if(Array.isArray(raw)) lista = raw;
    else if(raw && Array.isArray(raw.cnpjs)) lista = raw.cnpjs;
    else if(raw && Array.isArray(raw.data)) lista = raw.data;

    if(!lista.length){
      showAlert('alert-captacao','warn','Nenhum registro encontrado para esses filtros.');
      return;
    }
    const tbody = document.getElementById('preview-body');
    tbody.innerHTML = lista.slice(0,10).map(e=>`<tr>
      <td>${e.cnpj||'—'}</td>
      <td>${e.razao_social||'—'}</td>
      <td>${e.municipio||'—'}</td>
      <td>${(e.uf||'').toUpperCase()||'—'}</td>
      <td>${e.telefone_1||e.ddd_telefone_1||'—'}</td>
      <td>${e.email||'—'}</td>
    </tr>`).join('');
    document.getElementById('preview-card').style.display='block';
    showAlert('alert-captacao','ok',`${lista.length} registro(s) na prévia.`);
  } catch(e){
    showAlert('alert-captacao','error','Exceção: '+String(e));
  }
}

// ---- CAPTAR ----
async function captar(){
  clearAlert('alert-captacao');
  showAlert('alert-captacao','info','Enviando solicitação...');
  try {
    const r = await fetch('/api/captar',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(filtros())});
    const d = await r.json();
    if(d.ok){
      showAlert('alert-captacao','ok',
        `Arquivo solicitado! UUID: <b>${d.uuid}</b><br>
         <small>Aguarde alguns minutos e consulte a aba Solicitações.</small>`);
    } else {
      showAlert('alert-captacao','error','Falha: '+(d.msg||'Erro desconhecido'));
    }
  } catch(e){
    showAlert('alert-captacao','error','Exceção: '+String(e));
  }
}

// ---- SOLICITAÇÕES ----
async function listarSolicitacoes(){
  clearAlert('alert-sol');
  const container = document.getElementById('sol-body');
  container.innerHTML='<div style="text-align:center;color:#334155;padding:30px 0">Carregando...</div>';
  try {
    const r = await fetch('/api/solicitacoes');
    const d = await r.json();
    if(!d.ok){
      showAlert('alert-sol','error','Erro: '+(d.msg||''));
      container.innerHTML='';
      return;
    }

    // normaliza a lista — API pode retornar em vários formatos
    const raw = d.dados;
    let lista = [];
    if(Array.isArray(raw)) lista = raw;
    else if(raw && Array.isArray(raw.arquivos)) lista = raw.arquivos;
    else if(raw && Array.isArray(raw.data)) lista = raw.data;
    else if(raw && Array.isArray(raw.solicitacoes)) lista = raw.solicitacoes;

    if(!lista.length){
      container.innerHTML='<div style="text-align:center;color:#334155;padding:30px 0">Nenhuma solicitação encontrada.</div>';
      return;
    }

    // decide badge e se pode baixar
    function statusInfo(st){
      const s = (st||'').toLowerCase();
      // status "processado" da Casa dos Dados = arquivo pronto para download
      if(['processado','concluido','concluído','done','completed','pronto','finalizado'].some(x=>s.includes(x)))
        return {cls:'badge-green', pronto:true};
      if(['erro','error','fail','falha'].some(x=>s.includes(x)))
        return {cls:'badge-red', pronto:false};
      if(['processando','process','fila','queue','aguard','pend'].some(x=>s.includes(x)))
        return {cls:'badge-amber', pronto:false};
      // se não reconheceu mas tem algum status, trata como processando
      return {cls:'badge-amber', pronto:false};
    }

    const rows = lista.map(a=>{
      const uuid  = a.uuid || a.id || a.arquivo_uuid || '';
      const nome  = a.nome || a.name || (uuid?uuid.slice(0,12):'—');
      const st    = a.status || a.situacao || '';
      const info  = statusInfo(st);
      const linhas= a.total_linhas ?? a.linhas ?? a.quantidade ?? '—';
      const criado= a.criado_em || a.created_at || a.data_criacao || '—';
      const acao  = info.pronto
        ? `<a class="dl-link" href="/api/baixar-solicitacao/${uuid}" target="_blank">⬇ Baixar CSV</a>`
        : `<span style="color:#475569;font-size:12px">Aguardando...</span>`;
      return `<tr>
        <td>${nome}</td>
        <td><span class="badge ${info.cls}">${st||'?'}</span></td>
        <td style="font-size:12px;color:#475569">${criado}</td>
        <td style="font-size:12px">${linhas}</td>
        <td>${acao}</td>
      </tr>`;
    }).join('');

    container.innerHTML=`<div class="tbl-wrap"><table>
      <thead><tr><th>Nome</th><th>Status</th><th>Criado em</th><th>Linhas</th><th>Download</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  } catch(e){
    showAlert('alert-sol','error','Exceção: '+String(e));
    container.innerHTML='';
  }
}

// ---- USUÁRIOS ----
async function carregarUsuarios(){
  const r = await fetch('/api/admin/usuarios');
  const d = await r.json();
  if(!d.ok) return;
  document.getElementById('user-body').innerHTML = d.usuarios.map(u=>`<tr>
    <td>${u.id}</td>
    <td><b>${u.username}</b></td>
    <td>${u.is_admin?'<span class="badge badge-blue">Admin</span>':'<span class="badge badge-gray">Operador</span>'}</td>
    <td><input class="inp" id="pw-${u.id}" type="password" placeholder="Nova senha" style="max-width:150px">
        <button class="btn btn-secondary btn-sm" style="margin-left:6px" onclick="alterarSenha(${u.id})">Salvar</button></td>
    <td>${u.username==='admin'
      ? '<span style="color:#334155;font-size:12px">protegido</span>'
      : `<button class="btn btn-danger btn-sm" onclick="removerUsuario(${u.id},'${u.username}')">Remover</button>`
    }</td>
  </tr>`).join('');
}

async function criarUsuario(){
  clearAlert('alert-nu');
  const username=document.getElementById('nu-user').value.trim();
  const senha=document.getElementById('nu-senha').value;
  const is_admin=document.getElementById('nu-admin').value==='1';
  if(!username||!senha){ showAlert('alert-nu','warn','Preencha usuário e senha.'); return; }
  const r=await fetch('/api/admin/usuarios',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username,senha,is_admin})});
  const d=await r.json();
  if(d.ok){ showAlert('alert-nu','ok','Usuário criado!');
    document.getElementById('nu-user').value='';
    document.getElementById('nu-senha').value='';
    carregarUsuarios();
  } else { showAlert('alert-nu','error',d.msg); }
}

async function removerUsuario(id,nome){
  if(!confirm(`Remover "${nome}"?`)) return;
  const r=await fetch(`/api/admin/usuarios/${id}`,{method:'DELETE'});
  const d=await r.json();
  if(d.ok) carregarUsuarios();
  else showAlert('alert-user','error',d.msg);
}

async function alterarSenha(id){
  const senha=document.getElementById('pw-'+id).value;
  if(!senha){ showAlert('alert-user','warn','Digite a nova senha.'); return; }
  const r=await fetch(`/api/admin/usuarios/${id}/senha`,{method:'PUT',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({senha})});
  const d=await r.json();
  if(d.ok) showAlert('alert-user','ok','Senha alterada!');
  else showAlert('alert-user','error',d.msg);
}

// ---- CONFIGURAÇÕES ----
async function carregarCfgStats(){
  try {
    const r=await fetch('/api/saldo',{method:'POST'});
    const d=await r.json();
    const stEl=document.getElementById('cfg-status-api');
    const sdEl=document.getElementById('cfg-saldo');
    if(d.ok){
      stEl.textContent='Online'; stEl.className='stat-val green';
      const s=d.dados;
      const val = s.saldo_total ?? s.saldo ?? s.creditos ?? '—';
      sdEl.textContent = val !== '—' ? Number(val).toLocaleString('pt-BR') : '—';
    } else {
      stEl.textContent='Offline'; stEl.className='stat-val red';
      sdEl.textContent='—';
    }
  } catch(e){ }
  try {
    const kr=await fetch('/api/admin/apikey');
    const kd=await kr.json();
    const kEl=document.getElementById('cfg-key-status');
    if(kd.api_key){ kEl.textContent='OK'; kEl.className='stat-val green'; }
    else { kEl.textContent='Ausente'; kEl.className='stat-val red'; }
  } catch(e){ }
}

async function salvarKey(){
  const v=document.getElementById('cfg-key-input').value.trim();
  if(!v){ showAlert('alert-cfg','warn','Informe a chave.'); return; }
  const r=await fetch('/api/admin/apikey',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({api_key:v})});
  const d=await r.json();
  if(d.ok){ showAlert('alert-cfg','ok','API KEY salva!'); carregarCfgStats(); carregarSaldo(); }
  else showAlert('alert-cfg','error',d.msg);
}

async function verKey(){
  const r=await fetch('/api/admin/apikey');
  const d=await r.json();
  const msg=document.getElementById('cfg-key-msg');
  if(d.api_key){
    const k=d.api_key;
    msg.textContent='KEY: '+k.slice(0,8)+'*'.repeat(Math.max(0,k.length-8));
  } else { msg.textContent='Nenhuma KEY salva.'; }
}

async function testarConexao(){
  clearAlert('alert-cfg');
  showAlert('alert-cfg','info','Testando...');
  const r=await fetch('/api/saldo',{method:'POST'});
  const d=await r.json();
  if(d.ok) showAlert('alert-cfg','ok','Conexão OK! API respondendo normalmente.');
  else showAlert('alert-cfg','error','Falha: '+(d.msg||`HTTP ${d.status||'?'}`));
  carregarCfgStats();
}

async function diagnostico(){
  const div=document.getElementById('diag-body');
  div.innerHTML='<div style="color:#475569;font-size:13px">Rodando...</div>';
  const checks=[];
  const kr=await fetch('/api/admin/apikey');
  const kd=await kr.json();
  checks.push({ok:!!kd.api_key,label:'API KEY configurada',
    detalhe:kd.api_key?'Chave encontrada.':'Nenhuma API KEY salva.'});
  let sOk=false,sDet='';
  try {
    const sr=await fetch('/api/saldo',{method:'POST'});
    const sd=await sr.json();
    sOk=sd.ok; sDet=sd.ok?'API respondeu OK.':(sd.msg||`HTTP ${sd.status}`);
  } catch(e){ sDet=String(e); }
  checks.push({ok:sOk,label:'Conexão com Casa dos Dados',detalhe:sDet});
  let pOk=false,pDet='';
  try {
    const pr=await fetch('/api/previa',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({cnae:'6920601',situacao:'ATIVA'})});
    const pd=await pr.json();
    pOk=pd.ok; pDet=pd.ok?'Endpoint respondeu OK.':(pd.msg||'Erro');
  } catch(e){ pDet=String(e); }
  checks.push({ok:pOk,label:'Endpoint pesquisa CNPJ',detalhe:pDet});
  div.innerHTML=checks.map(c=>`
    <div class="alert ${c.ok?'alert-ok':'alert-error'}" style="margin-bottom:8px">
      <span>${c.ok?'✓':'✗'}</span>
      <div><b>${c.label}</b><br><span style="font-size:12px;opacity:.8">${c.detalhe}</span></div>
    </div>`).join('');
}

// ---- LOGS ----
async function carregarLogs(){
  const r=await fetch('/api/admin/logs');
  const d=await r.json();
  allLogs=d.logs||[];
  renderLogs();
  document.getElementById('log-count').textContent=allLogs.length;
  document.getElementById('log-errors').textContent=allLogs.filter(l=>l.level==='ERROR').length;
  document.getElementById('log-warns').textContent=allLogs.filter(l=>l.level==='WARN').length;
  document.getElementById('log-infos').textContent=allLogs.filter(l=>l.level==='INFO').length;
}

function renderLogs(){
  const panel=document.getElementById('log-panel');
  const f=logFiltro==='ALL'?allLogs:allLogs.filter(l=>l.level===logFiltro);
  if(!f.length){ panel.innerHTML='<div class="log-empty">Nenhum log para este filtro.</div>'; return; }
  panel.innerHTML=[...f].reverse().map(l=>`
    <div class="log-row">
      <span class="log-ts">${l.ts}</span>
      <span class="log-lv ${l.level}">${l.level}</span>
      <span class="log-orig">${l.origem}</span>
      <div style="flex:1">
        <div class="log-msg">${l.msg}</div>
        ${l.detalhe?`<div class="log-det">${l.detalhe}</div>`:''}
      </div>
    </div>`).join('');
}

function setFiltro(f){
  logFiltro=f;
  ['ALL','ERROR','WARN','INFO'].forEach(x=>{
    document.getElementById('f-'+x).classList.toggle('on',x===f);
  });
  renderLogs();
}

async function limparLogs(){
  if(!confirm('Limpar todos os logs?')) return;
  await fetch('/api/admin/logs',{method:'DELETE'});
  allLogs=[];
  renderLogs();
  ['log-count','log-errors','log-warns','log-infos'].forEach(id=>{
    document.getElementById(id).textContent='0';
  });
}
</script>
</body>
</html>"""

# =========================================================
# ROUTES — AUTH
# =========================================================

@app.route("/")
def index():
    if not session.get("uid"):
        return Response(HTML_LOGIN, content_type="text/html; charset=utf-8")
    return Response(HTML_APP, content_type="text/html; charset=utf-8")

@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.json or {}
    u = autenticar(d.get("username","").strip(), d.get("senha",""))
    if not u:
        add_log("WARN","login",f"Tentativa falha: {d.get('username','')}")
        return jsonify({"ok":False,"msg":"Usuário ou senha incorretos."})
    session["uid"]      = u["id"]
    session["username"] = u["username"]
    session["is_admin"] = u["is_admin"]
    add_log("INFO","login",f"Login: {u['username']}")
    return jsonify({"ok":True,"is_admin":u["is_admin"]})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    add_log("INFO","login",f"Logout: {session.get('username','?')}")
    session.clear()
    return jsonify({"ok":True})

@app.route("/api/eu")
@login_required
def api_eu():
    return jsonify({"ok":True,"username":session["username"],"is_admin":session["is_admin"]})

# =========================================================
# ROUTES — ADMIN USUÁRIOS
# =========================================================

@app.route("/api/admin/usuarios", methods=["GET"])
@login_required
@admin_required
def admin_get_usuarios():
    return jsonify({"ok":True,"usuarios":listar_usuarios()})

@app.route("/api/admin/usuarios", methods=["POST"])
@login_required
@admin_required
def admin_criar_usuario():
    d = request.json or {}
    ok, msg = criar_usuario(d.get("username",""), d.get("senha",""), d.get("is_admin",False))
    if ok: add_log("INFO","usuarios",f"Usuário criado: {d.get('username')}")
    else:  add_log("WARN","usuarios",f"Falha criar: {d.get('username')}",msg)
    return jsonify({"ok":ok,"msg":msg})

@app.route("/api/admin/usuarios/<int:uid>", methods=["DELETE"])
@login_required
@admin_required
def admin_remover_usuario(uid):
    ok, msg = remover_usuario(uid)
    if ok: add_log("INFO","usuarios",f"Removido id={uid}")
    else:  add_log("WARN","usuarios",f"Falha remover id={uid}",msg)
    return jsonify({"ok":ok,"msg":msg})

@app.route("/api/admin/usuarios/<int:uid>/senha", methods=["PUT"])
@login_required
@admin_required
def admin_alterar_senha(uid):
    d = request.json or {}
    ok, msg = alterar_senha(uid, d.get("senha",""))
    if ok: add_log("INFO","usuarios",f"Senha alterada id={uid}")
    else:  add_log("WARN","usuarios",f"Falha senha id={uid}",msg)
    return jsonify({"ok":ok,"msg":msg})

# =========================================================
# ROUTES — API KEY
# =========================================================

@app.route("/api/admin/apikey", methods=["GET"])
@login_required
@admin_required
def admin_get_key():
    return jsonify({"ok":True,"api_key":get_api_key()})

@app.route("/api/admin/apikey", methods=["POST"])
@login_required
@admin_required
def admin_set_key():
    d = request.json or {}
    key = d.get("api_key","").strip()
    if not key:
        return jsonify({"ok":False,"msg":"Informe a chave."})
    set_api_key(key)
    add_log("INFO","config","API KEY atualizada")
    return jsonify({"ok":True})

# =========================================================
# ROUTES — LOGS
# =========================================================

@app.route("/api/admin/logs")
@login_required
@admin_required
def admin_get_logs():
    return jsonify({"ok":True,"logs":_LOGS})

@app.route("/api/admin/logs", methods=["DELETE"])
@login_required
@admin_required
def admin_clear_logs():
    _LOGS.clear()
    return jsonify({"ok":True})

# =========================================================
# ROUTES — SALDO
# =========================================================

@app.route("/api/saldo", methods=["POST"])
@login_required
def api_saldo():
    key = get_api_key()
    if not key:
        add_log("WARN","saldo","API KEY não configurada")
        return jsonify({"ok":False,"msg":"API KEY não configurada."})
    try:
        r = requests.get(ENDPOINT_SALDO, headers=_h(key), timeout=20)
        ok = r.status_code == 200
        dados = {}
        try: dados = r.json()
        except: pass
        if not ok:
            add_log("ERROR","saldo",f"HTTP {r.status_code}",r.text[:200])
        return jsonify({"ok":ok,"status":r.status_code,"dados":dados})
    except Exception as e:
        add_log("ERROR","saldo","Exceção",str(e))
        return jsonify({"ok":False,"msg":str(e)})

# =========================================================
# ROUTES — PRÉVIA
# =========================================================

@app.route("/api/previa", methods=["POST"])
@login_required
def api_previa():
    key = get_api_key()
    if not key:
        add_log("WARN","previa","API KEY não configurada")
        return jsonify({"ok":False,"msg":"Configure a API KEY."})
    d = request.json or {}
    pesquisa = montar_pesquisa(d)
    add_log("INFO","previa",f"Solicitada por {session.get('username')}",str(pesquisa)[:200])
    try:
        r = requests.post(ENDPOINT_PESQUISA, json=pesquisa, headers=_h(key), timeout=30)
        ok = r.status_code == 200
        dados = {}
        try: dados = r.json()
        except: pass
        if not ok:
            add_log("ERROR","previa",f"HTTP {r.status_code}",r.text[:300])
        else:
            # loga quantos registros vieram
            raw = dados
            cnt = 0
            if isinstance(raw, list): cnt = len(raw)
            elif isinstance(raw, dict):
                cnt = len(raw.get("cnpjs") or raw.get("data") or [])
            add_log("INFO","previa",f"Retornou {cnt} registros")
        return jsonify({"ok":ok,"dados":dados})
    except Exception as e:
        add_log("ERROR","previa","Exceção",str(e))
        return jsonify({"ok":False,"msg":str(e)})

# =========================================================
# ROUTES — CAPTAR
# =========================================================

@app.route("/api/captar", methods=["POST"])
@login_required
def api_captar():
    key = get_api_key()
    if not key:
        add_log("WARN","captar","API KEY não configurada")
        return jsonify({"ok":False,"msg":"Configure a API KEY."})
    d = request.json or {}
    payload = {
        "total_linhas": 0,
        "nome": d.get("nome","captacao"),
        "tipo": "csv",
        "pesquisa": montar_pesquisa(d),
    }
    add_log("INFO","captar",f"Iniciada por {session.get('username')}",str(payload.get('pesquisa',''))[:200])
    try:
        r = requests.post(ENDPOINT_GERAR, json=payload, headers=_h(key), timeout=30)
    except requests.exceptions.RequestException as e:
        add_log("ERROR","captar","Erro conexão",str(e))
        return jsonify({"ok":False,"msg":str(e)})
    if r.status_code not in (200,201,202):
        add_log("ERROR","captar",f"HTTP {r.status_code}",r.text[:300])
        return jsonify({"ok":False,"msg":f"HTTP {r.status_code}"})
    try: body = r.json()
    except:
        add_log("ERROR","captar","Resposta inválida")
        return jsonify({"ok":False,"msg":"Resposta inválida"})
    uuid = body.get("arquivo_uuid") or body.get("uuid")
    if not uuid:
        add_log("ERROR","captar","UUID não retornado",str(body)[:200])
        return jsonify({"ok":False,"msg":"UUID não retornado"})
    add_log("INFO","captar",f"Arquivo gerado: {uuid}")
    return jsonify({"ok":True,"uuid":uuid})

# =========================================================
# ROUTES — SOLICITAÇÕES
# =========================================================

@app.route("/api/solicitacoes")
@login_required
def api_solicitacoes():
    key = get_api_key()
    if not key:
        add_log("WARN","solicitacoes","API KEY não configurada")
        return jsonify({"ok":False,"msg":"Configure a API KEY."})
    try:
        r = requests.get(ENDPOINT_LISTAR, headers=_h(key), timeout=25)
        ok = r.status_code == 200
        dados = {}
        try: dados = r.json()
        except: pass
        if not ok:
            add_log("ERROR","solicitacoes",f"HTTP {r.status_code}",r.text[:200])
        else:
            add_log("INFO","solicitacoes","Lista atualizada com sucesso")
        return jsonify({"ok":ok,"dados":dados})
    except Exception as e:
        add_log("ERROR","solicitacoes","Exceção",str(e))
        return jsonify({"ok":False,"msg":str(e)})

# =========================================================
# ROUTES — DOWNLOAD
# =========================================================

@app.route("/api/baixar-solicitacao/<uuid>")
@login_required
def baixar(uuid):
    """
    A API Casa dos Dados v4/public retorna o arquivo ZIP diretamente no body
    (começa com PK — assinatura ZIP). Não há JSON com link — é o binário mesmo.
    """
    key = get_api_key()
    if not key:
        return "API KEY não configurada.", 400

    add_log("INFO", "download", f"Solicitado: {uuid} por {session.get('username')}")

    url = f"https://api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo/{uuid}"

    try:
        r = requests.get(url, headers=_h(key), timeout=120, stream=True)
    except Exception as e:
        add_log("ERROR", "download", f"Erro de conexão para {uuid}", str(e))
        return str(e), 500

    if r.status_code == 425:
        add_log("WARN", "download", f"Arquivo ainda processando: {uuid}")
        return "Arquivo ainda processando. Aguarde e tente novamente.", 425

    if r.status_code != 200:
        add_log("ERROR", "download", f"HTTP {r.status_code} para {uuid}", r.text[:200])
        return f"Erro HTTP {r.status_code}.", r.status_code

    # Detecta pelo Content-Type ou pelo início do corpo se é ZIP ou JSON
    content_type = r.headers.get("Content-Type", "")
    filename_zip = f"captacao_{uuid[:8]}.zip"
    filename_csv = f"captacao_{uuid[:8]}.csv"

    # Lê os primeiros bytes para identificar o tipo
    conteudo = r.content  # carrega tudo (arquivos são pequenos em plano gratuito)

    if conteudo[:2] == b"PK":
        # É um ZIP — entrega direto
        add_log("INFO", "download", f"ZIP recebido, entregando: {filename_zip}")
        return Response(
            conteudo,
            content_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename_zip}"'},
        )

    # Tenta interpretar como JSON (pode ter um campo com link)
    try:
        body = json.loads(conteudo)
        link = (
            body.get("link")
            or body.get("url")
            or body.get("download_url")
            or body.get("arquivo_url")
        )
        if link:
            add_log("INFO", "download", f"Link encontrado no JSON: {link[:80]}")
            csv_r = requests.get(link, timeout=120, stream=True)
            if csv_r.status_code == 200:
                return Response(
                    csv_r.iter_content(chunk_size=8192),
                    content_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename_csv}"'},
                )
            return redirect(link)
        else:
            add_log("WARN", "download", f"JSON sem link para {uuid}", str(body)[:200])
            return "Arquivo ainda processando. Aguarde e tente novamente.", 425
    except Exception:
        pass

    # Se chegou aqui, entrega o conteúdo como CSV mesmo
    add_log("INFO", "download", f"Entregando conteúdo bruto como CSV: {filename_csv}")
    return Response(
        conteudo,
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename_csv}"'},
    )

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


# DEBUG — mostra resposta bruta da API para um UUID (admin only)
# Use: https://captador-cnpj.onrender.com/api/debug-arquivo/<UUID>
@app.route("/api/debug-arquivo/<uuid>")
@login_required
@admin_required
def debug_arquivo(uuid):
    key = get_api_key()
    if not key:
        return jsonify({"erro": "Sem API KEY"})
    resultados = []
    endpoints = [
        f"https://api.casadosdados.com.br/v5/cnpj/pesquisa/arquivo/{uuid}",
        f"https://api.casadosdados.com.br/v4/cnpj/pesquisa/arquivo/{uuid}",
        f"https://api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo/{uuid}",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers=_h(key), timeout=15)
            try:
                body = r.json()
            except Exception:
                body = r.text[:800]
            resultados.append({"url": url, "status": r.status_code, "body": body})
        except Exception as e:
            resultados.append({"url": url, "erro": str(e)})
    return jsonify(resultados)
