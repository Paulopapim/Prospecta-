"""
Captador de CNPJs — Casa dos Dados
"""

import io
import os
import secrets
import sqlite3
from functools import wraps

import requests
from flask import (
    Flask,
    jsonify,
    request,
    send_file,
    Response,
    session,
    redirect,
)

# =========================================================
# APP
# =========================================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DB_PATH = os.environ.get("DB_PATH", "database.db")

ENDPOINT_GERAR    = "https://api.casadosdados.com.br/v5/cnpj/pesquisa/arquivo"
ENDPOINT_CONSULTAR = "https://api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo"
ENDPOINT_LISTAR   = "https://api.casadosdados.com.br/v4/cnpj/pesquisa/arquivo"
ENDPOINT_PESQUISA = "https://api.casadosdados.com.br/v5/cnpj/pesquisa"
ENDPOINT_SALDO    = "https://api.casadosdados.com.br/v5/saldo"

# =========================================================
# DATABASE
# =========================================================

def conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    c = conn()
    cur = c.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        senha    TEXT,
        is_admin INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS config (
        chave TEXT PRIMARY KEY,
        valor TEXT
    )
    """)

    if not cur.execute("SELECT 1 FROM usuarios WHERE username='admin'").fetchone():
        cur.execute("""
        INSERT INTO usuarios(username, senha, is_admin)
        VALUES('admin','admin123',1)
        """)

    c.commit()
    c.close()


init_db()

# =========================================================
# HELPERS DB
# =========================================================

def auth(username, senha):
    c = conn()
    cur = c.cursor()
    cur.execute("""
        SELECT id, username, is_admin
        FROM usuarios WHERE username=? AND senha=?
    """, (username, senha))
    r = cur.fetchone()
    c.close()
    if not r:
        return None
    return {"id": r[0], "username": r[1], "is_admin": bool(r[2])}


def get_api_key():
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT valor FROM config WHERE chave='api_key'")
    r = cur.fetchone()
    c.close()
    return r[0] if r else ""


def set_api_key(v):
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT OR REPLACE INTO config(chave,valor) VALUES('api_key',?)", (v,))
    c.commit()
    c.close()

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


def _headers(key):
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
# HTML
# =========================================================

HTML_LOGIN = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login — Captador CNPJ</title>
<link rel="icon" href="data:,">
<style>
*{box-sizing:border-box}
body{background:#0f172a;color:#fff;font-family:Arial,sans-serif;display:flex;
     justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#111827;padding:40px;border-radius:12px;width:320px}
h2{margin:0 0 20px}
input{width:100%;padding:12px;margin-top:10px;border:none;border-radius:8px;
      background:#1f2937;color:#fff;font-size:14px}
button{width:100%;padding:12px;margin-top:16px;border:none;border-radius:8px;
       background:#84cc16;font-weight:bold;cursor:pointer;font-size:15px}
#erro{margin-top:12px;color:#fb7185;font-size:13px}
</style>
</head>
<body>
<div class="box">
  <h2>Captador CNPJ</h2>
  <input id="u" placeholder="Usuário">
  <input id="s" type="password" placeholder="Senha">
  <button onclick="entrar()">Entrar</button>
  <div id="erro"></div>
</div>
<script>
async function entrar(){
  const r = await fetch('/api/login',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('u').value,
                         senha:document.getElementById('s').value})});
  const d = await r.json();
  if(d.ok) location.reload();
  else document.getElementById('erro').innerText = d.msg;
}
document.addEventListener('keydown',e=>{ if(e.key==='Enter') entrar(); });
</script>
</body>
</html>"""

HTML_APP = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Captador CNPJ</title>
<link rel="icon" href="data:,">
<style>
*{box-sizing:border-box}
body{background:#0f172a;color:#fff;font-family:Arial,sans-serif;margin:0;padding:20px}
.wrap{max-width:960px;margin:auto}
.card{background:#111827;padding:24px;border-radius:12px;margin-bottom:20px}
h1{margin:0 0 4px;font-size:22px}
label{font-size:13px;color:#9ca3af;display:block;margin-top:14px}
input,select{width:100%;padding:10px;margin-top:4px;border:none;border-radius:8px;
             background:#1f2937;color:#fff;font-size:14px}
.row{display:flex;gap:10px;flex-wrap:wrap}
.row>div{flex:1;min-width:160px}
.btns{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
button{padding:10px 18px;border:none;border-radius:8px;background:#84cc16;
       font-weight:bold;cursor:pointer;font-size:14px}
button.sec{background:#374151;color:#fff}
button.danger{background:#ef4444;color:#fff}
#log{margin-top:16px;white-space:pre-wrap;background:#0b1220;padding:14px;
     border-radius:8px;font-size:13px;display:none;max-height:300px;overflow-y:auto}
#log.show{display:block}
table{width:100%;margin-top:16px;border-collapse:collapse;font-size:13px}
th,td{border:1px solid #374151;padding:8px;text-align:left}
th{background:#1f2937}
a.dl{color:#84cc16;text-decoration:none;font-weight:bold}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold}
.tag.pronto{background:#16a34a}
.tag.proc{background:#ca8a04}
.tag.erro{background:#dc2626}
</style>
</head>
<body>
<div class="wrap">

<div class="card">
  <h1>📋 Captador de CNPJs</h1>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
    <span id="saldo_txt" style="font-size:13px;color:#9ca3af">—</span>
    <div style="display:flex;gap:8px">
      <button class="sec" onclick="carregarSaldo()">Atualizar saldo</button>
      <button class="danger" onclick="logout()">Sair</button>
    </div>
  </div>
</div>

<div class="card">
  <h3 style="margin:0 0 12px">Filtros</h3>
  <div class="row">
    <div>
      <label>CNAE(s) — separados por vírgula</label>
      <input id="cnae" value="6920601">
    </div>
    <div>
      <label>Situação cadastral</label>
      <select id="situacao">
        <option value="ATIVA">ATIVA</option>
        <option value="BAIXADA">BAIXADA</option>
        <option value="INAPTA">INAPTA</option>
        <option value="SUSPENSA">SUSPENSA</option>
      </select>
    </div>
  </div>
  <div class="row">
    <div>
      <label>UF(s) — ex: sp,rj</label>
      <input id="ufs" placeholder="Todas">
    </div>
    <div>
      <label>Município(s)</label>
      <input id="municipios" placeholder="Todos">
    </div>
    <div>
      <label>Últimos N dias (abertura)</label>
      <input id="ultimos_dias" type="number" placeholder="0 = ignorar">
    </div>
  </div>
  <div class="row">
    <div>
      <label>Total de linhas (0 = máx)</label>
      <input id="total_linhas" type="number" placeholder="0">
    </div>
    <div>
      <label>Nome do arquivo</label>
      <input id="nome" value="captacao">
    </div>
  </div>
  <div style="margin-top:12px;display:flex;gap:18px;font-size:13px">
    <label style="display:flex;align-items:center;gap:6px;margin:0">
      <input type="checkbox" id="somente_mei"> Somente MEI
    </label>
    <label style="display:flex;align-items:center;gap:6px;margin:0">
      <input type="checkbox" id="com_telefone"> Com telefone
    </label>
    <label style="display:flex;align-items:center;gap:6px;margin:0">
      <input type="checkbox" id="com_email"> Com e-mail
    </label>
  </div>
  <div class="btns">
    <button onclick="previa()">🔍 Prévia (5 registros)</button>
    <button onclick="captar()">📤 Gerar Arquivo</button>
  </div>
  <pre id="log"></pre>
  <div id="previa_div"></div>
</div>

<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <h3 style="margin:0">Solicitações geradas</h3>
    <button class="sec" onclick="listarSolicitacoes()">🔄 Atualizar lista</button>
  </div>
  <div id="solicitacoes_div" style="margin-top:12px;font-size:13px;color:#9ca3af">
    Clique em "Atualizar lista" para carregar.
  </div>
</div>

<div id="admin_card" class="card" style="display:none">
  <h3 style="margin:0 0 12px">⚙️ Admin — API KEY</h3>
  <input id="apikey_input" type="password" placeholder="Cole sua API KEY aqui">
  <div class="btns">
    <button onclick="salvarKey()">💾 Salvar API KEY</button>
    <button class="sec" onclick="verKey()">👁 Ver KEY atual</button>
  </div>
  <div id="key_msg" style="margin-top:8px;font-size:13px"></div>
</div>

</div><!-- wrap -->

<script>

// ---- uteis ----

function filtros(){
  return {
    cnae:          document.getElementById('cnae').value,
    situacao:      document.getElementById('situacao').value,
    ufs:           document.getElementById('ufs').value,
    municipios:    document.getElementById('municipios').value,
    ultimos_dias:  document.getElementById('ultimos_dias').value,
    total_linhas:  document.getElementById('total_linhas').value,
    nome:          document.getElementById('nome').value,
    somente_mei:   document.getElementById('somente_mei').checked,
    com_telefone:  document.getElementById('com_telefone').checked,
    com_email:     document.getElementById('com_email').checked,
  };
}

function log(txt){
  const el = document.getElementById('log');
  el.classList.add('show');
  el.textContent = txt;
}

function appendLog(txt){
  const el = document.getElementById('log');
  el.classList.add('show');
  el.textContent += txt + '\\n';
}

// ---- init ----

(async()=>{
  const r = await fetch('/api/eu');
  if(!r.ok) return;
  const d = await r.json();
  if(d.is_admin) document.getElementById('admin_card').style.display='block';
  carregarSaldo();
})();

// ---- saldo ----

async function carregarSaldo(){
  const r = await fetch('/api/saldo',{method:'POST'});
  const d = await r.json();
  const el = document.getElementById('saldo_txt');
  if(d.ok && d.dados){
    const s = d.dados;
    el.textContent = `Saldo: ${s.saldo ?? s.creditos ?? JSON.stringify(s)}`;
  } else {
    el.textContent = 'Saldo indisponível';
  }
}

// ---- logout ----

async function logout(){
  await fetch('/api/logout',{method:'POST'});
  location.reload();
}

// ---- prévia ----

async function previa(){
  log('Buscando prévia...');
  document.getElementById('previa_div').innerHTML='';
  const r = await fetch('/api/previa',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(filtros())});
  const d = await r.json();
  if(!d.ok){ log('❌ ' + (d.msg||'Erro')); return; }

  const registros = d.dados?.cnpjs || d.dados?.data || d.dados || [];
  if(!registros.length){ log('Nenhum registro encontrado.'); return; }

  let h = '<table><tr><th>CNPJ</th><th>Razão Social</th><th>Município</th><th>UF</th></tr>';
  registros.slice(0,10).forEach(e=>{
    h += `<tr><td>${e.cnpj||''}</td><td>${e.razao_social||''}</td>
          <td>${e.municipio||''}</td><td>${e.uf||''}</td></tr>`;
  });
  h += '</table>';
  document.getElementById('previa_div').innerHTML = h;
  log(`✅ ${registros.length} registro(s) exibido(s).`);
}

// ---- captar ----

async function captar(){
  log('Enviando solicitação...');
  const r = await fetch('/api/captar',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(filtros())});
  const d = await r.json();
  if(d.log) d.log.forEach(l => appendLog(l));
  if(d.ok){
    appendLog('✅ Arquivo solicitado. UUID: ' + d.uuid);
    appendLog('Aguarde alguns minutos e clique em "Atualizar lista".');
  } else {
    appendLog('❌ ' + (d.msg||'Erro'));
  }
}

// ---- listar solicitações ----

async function listarSolicitacoes(){
  const div = document.getElementById('solicitacoes_div');
  div.textContent = 'Carregando...';
  const r = await fetch('/api/solicitacoes');
  const d = await r.json();
  if(!d.ok){ div.textContent = '❌ ' + (d.msg||'Erro'); return; }

  const lista = d.dados?.arquivos || d.dados?.data || d.dados || [];
  if(!lista.length){ div.textContent = 'Nenhuma solicitação encontrada.'; return; }

  let h = `<table>
    <tr><th>Nome</th><th>Status</th><th>Criado em</th><th>Linhas</th><th>Ação</th></tr>`;
  lista.forEach(a=>{
    const uuid   = a.uuid || a.id || '';
    const nome   = a.nome || a.name || uuid;
    const status = (a.status||'').toLowerCase();
    const linhas = a.total_linhas ?? a.linhas ?? '—';
    const criado = a.criado_em || a.created_at || '—';

    let tagClass = status.includes('conclu') || status.includes('pronto') || status==='done'
                   ? 'pronto' : status.includes('erro') ? 'erro' : 'proc';

    let acao = '—';
    if(tagClass==='pronto'){
      acao = `<a class="dl" href="/api/baixar-solicitacao/${uuid}" target="_blank">⬇ Baixar</a>`;
    } else if(tagClass==='proc'){
      acao = `<span style="color:#9ca3af">Processando...</span>`;
    }

    h += `<tr>
      <td>${nome}</td>
      <td><span class="tag ${tagClass}">${status||'?'}</span></td>
      <td>${criado}</td>
      <td>${linhas}</td>
      <td>${acao}</td>
    </tr>`;
  });
  h += '</table>';
  div.innerHTML = h;
}

// ---- admin ----

async function salvarKey(){
  const v = document.getElementById('apikey_input').value.trim();
  if(!v){ document.getElementById('key_msg').textContent='⚠️ Informe a chave.'; return; }
  const r = await fetch('/api/admin/apikey',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({api_key:v})});
  const d = await r.json();
  document.getElementById('key_msg').textContent = d.ok ? '✅ Salvo!' : '❌ ' + d.msg;
}

async function verKey(){
  const r = await fetch('/api/admin/apikey');
  const d = await r.json();
  const k = d.api_key;
  document.getElementById('key_msg').textContent =
    k ? `KEY atual: ${k.slice(0,6)}${'*'.repeat(Math.max(0,k.length-6))}` : 'Nenhuma KEY salva.';
}

</script>
</body>
</html>"""


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def index():
    if not session.get("uid"):
        return Response(HTML_LOGIN, content_type="text/html; charset=utf-8")
    return Response(HTML_APP, content_type="text/html; charset=utf-8")


@app.route("/favicon.ico")
def favicon():
    return "", 204


# ---- auth ----

@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.json or {}
    u = auth(d.get("username", "").strip(), d.get("senha", ""))
    if not u:
        return jsonify({"ok": False, "msg": "Usuário ou senha incorretos."})
    session["uid"]      = u["id"]
    session["username"] = u["username"]
    session["is_admin"] = u["is_admin"]
    return jsonify({"ok": True, "is_admin": u["is_admin"]})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/eu")
@login_required
def api_eu():
    return jsonify({
        "ok": True,
        "username": session["username"],
        "is_admin": session["is_admin"],
    })


# ---- admin ----

@app.route("/api/admin/apikey", methods=["GET"])
@login_required
@admin_required
def admin_get_key():
    return jsonify({"ok": True, "api_key": get_api_key()})


@app.route("/api/admin/apikey", methods=["POST"])
@login_required
@admin_required
def admin_set_key():
    d = request.json or {}
    key = d.get("api_key", "").strip()
    if not key:
        return jsonify({"ok": False, "msg": "Informe a chave."})
    set_api_key(key)
    return jsonify({"ok": True})


# ---- saldo ----

@app.route("/api/saldo", methods=["POST"])
@login_required
def api_saldo():
    key = get_api_key()
    if not key:
        return jsonify({"ok": False, "msg": "API KEY não configurada."})
    try:
        r = requests.get(ENDPOINT_SALDO, headers=_headers(key), timeout=20)
        return jsonify({"ok": r.status_code == 200, "status": r.status_code, "dados": r.json()})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


# ---- prévia ----

@app.route("/api/previa", methods=["POST"])
@login_required
def api_previa():
    key = get_api_key()
    if not key:
        return jsonify({"ok": False, "msg": "Configure a API KEY."})
    d = request.json or {}
    pesquisa = montar_pesquisa(d)
    try:
        r = requests.post(ENDPOINT_PESQUISA, json=pesquisa, headers=_headers(key), timeout=30)
        return jsonify({"ok": r.status_code == 200, "dados": r.json()})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


# ---- captar ----

@app.route("/api/captar", methods=["POST"])
@login_required
def api_captar():
    key = get_api_key()
    if not key:
        return jsonify({"ok": False, "msg": "Configure a API KEY."})
    d = request.json or {}
    msgs = []

    payload = {
        "total_linhas": 0,
        "nome": d.get("nome", "captacao"),
        "tipo": "csv",
        "pesquisa": montar_pesquisa(d),
    }

    msgs.append("📤 Enviando solicitação...")

    try:
        r = requests.post(ENDPOINT_GERAR, json=payload, headers=_headers(key), timeout=30)
    except requests.exceptions.RequestException as e:
        msgs.append(f"❌ Erro de conexão: {e}")
        return jsonify({"ok": False, "msg": str(e), "log": msgs})

    if r.status_code not in (200, 201, 202):
        msgs.append(f"❌ HTTP {r.status_code}: {r.text[:200]}")
        return jsonify({"ok": False, "msg": f"HTTP {r.status_code}", "log": msgs})

    try:
        body = r.json()
    except Exception:
        msgs.append("❌ Resposta inválida da API.")
        return jsonify({"ok": False, "msg": "Resposta inválida", "log": msgs})

    uuid = body.get("arquivo_uuid") or body.get("uuid")
    if not uuid:
        msgs.append(f"❌ UUID não retornado. Resposta: {body}")
        return jsonify({"ok": False, "msg": "UUID não retornado", "log": msgs})

    msgs.append(f"✅ UUID: {uuid}")
    return jsonify({"ok": True, "uuid": uuid, "log": msgs})


# ---- listar solicitações ----

@app.route("/api/solicitacoes")
@login_required
def api_solicitacoes():
    key = get_api_key()
    if not key:
        return jsonify({"ok": False, "msg": "Configure a API KEY."})
    try:
        r = requests.get(ENDPOINT_LISTAR, headers=_headers(key), timeout=25)
        return jsonify({"ok": r.status_code == 200, "dados": r.json()})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


# ---- baixar arquivo ----

@app.route("/api/baixar-solicitacao/<uuid>")
@login_required
def baixar(uuid):
    """
    Consulta o status do arquivo na API Casa dos Dados.
    Se tiver link de download, faz proxy do CSV para o navegador
    (evita problema de CORS / redirect para domínio externo).
    """
    key = get_api_key()
    if not key:
        return "API KEY não configurada.", 400

    try:
        r = requests.get(
            f"{ENDPOINT_CONSULTAR}/{uuid}",
            headers=_headers(key),
            timeout=30,
        )
    except Exception as e:
        return str(e), 500

    if r.status_code == 425:
        return "Arquivo ainda processando. Aguarde e tente novamente.", 425

    if r.status_code != 200:
        return f"Erro HTTP {r.status_code} ao consultar arquivo.", r.status_code

    try:
        body = r.json()
    except Exception:
        return "Resposta inválida da API.", 500

    link = body.get("link") or body.get("url") or body.get("download_url")

    if not link:
        # Arquivo ainda não está pronto
        return "Arquivo ainda processando. Aguarde e tente novamente.", 425

    # Faz proxy do arquivo para o cliente (download direto sem redirect externo)
    try:
        csv_r = requests.get(link, timeout=60, stream=True)
        if csv_r.status_code != 200:
            # Fallback: redireciona para o link externo
            return redirect(link)

        filename = f"captacao_{uuid[:8]}.csv"
        return Response(
            csv_r.iter_content(chunk_size=8192),
            content_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )
    except Exception:
        # Se o proxy falhar, tenta redirect direto
        return redirect(link)


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
