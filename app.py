"""
Captador de CNPJs — Casa dos Dados v5 (Web com gestão de usuários)
====================================================================

Site privado para você e sua equipe:
- Login por usuário/senha (cada pessoa o seu)
- Painel ADMIN: cadastrar/remover usuários e TROCAR a chave de API
- A chave de API fica guardada de forma central; usuários comuns
nem a veem — só usam a ferramenta.
- Modo teste rápido agora também PRÉ-VISUALIZA os 5 CNPJs na tela
(resolve a dependência do download de arquivo).

Primeiro acesso (admin padrão):
usuário: admin / senha: admin123
>>> TROQUE a senha do admin logo no primeiro login. <<<
"""

import io
import os
import time
import secrets
from functools import wraps
from datetime import datetime

import requests
from flask import (Flask, request, jsonify, send_file, Response,
                    session, redirect)

import db

ENDPOINT_GERAR = "https://api.casadosdados.com.br/v5/cnpj/pesquisa/arquivo"
ENDPOINT_CONSULTAR = "https://api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo"
ENDPOINT_LISTAR = "https://api.casadosdados.com.br/v4/cnpj/pesquisa/arquivo"
ENDPOINT_PESQUISA = "https://api.casadosdados.com.br/v5/cnpj/pesquisa"
ENDPOINT_SALDO = "https://api.casadosdados.com.br/v5/saldo"
POLL_INTERVALO = 5
POLL_MAX = 60

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
db.init_db()

_ARQUIVOS = {}


def login_obrigatorio(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("uid"):
            return jsonify({"ok": False, "msg": "Faça login."}), 401
        return f(*a, **k)
    return w


def admin_obrigatorio(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("is_admin"):
            return jsonify({"ok": False, "msg": "Acesso restrito ao admin."}), 403
        return f(*a, **k)
    return w


def _h(key):
    return {"api-key": key, "Content-Type": "application/json"}


def montar_pesquisa(d):
    p = {
        "codigo_atividade_principal":
            [c.strip() for c in d.get("cnae", "").split(",") if c.strip()],
        "situacao_cadastral": [d.get("situacao") or "ATIVA"],
    }
    if d.get("ufs"):
        p["uf"] = [u.strip().lower() for u in d["ufs"].split(",") if u.strip()]
    if d.get("municipios"):
        p["municipio"] = [m.strip().lower()
                          for m in d["municipios"].split(",") if m.strip()]
    if d.get("ultimos_dias") and int(d["ultimos_dias"]) > 0:
        p["data_abertura"] = {"ultimos_dias": int(d["ultimos_dias"])}
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
    except (TypeError, ValueError):
        lim = 0
    if lim and 1 <= lim <= 1000:
        p["limite"] = lim
    return p


def gerar_e_baixar(api_key, nome, pesquisa, tipo, total_linhas, log):
    payload = {"total_linhas": int(total_linhas), "nome": nome,
               "tipo": "csv", "pesquisa": pesquisa}
    log("📤 Enviando solicitação...")
    try:
        r = requests.post(ENDPOINT_GERAR, json=payload,
                          headers=_h(api_key), timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"❌ Erro de conexão: {e}"); return None
    if r.status_code == 401:
        log("❌ Chave de API inválida (401)."); return None
    if r.status_code == 403:
        log("❌ Sem saldo/permissão (403)."); return None
    if r.status_code not in (200, 201, 202):
        try:
            detalhe = r.json()
            detalhe = (detalhe.get("mensagem") or detalhe.get("message")
                       or detalhe.get("detail") or str(detalhe))
        except Exception:
            detalhe = (r.text or "")[:300]
        log(f"❌ HTTP {r.status_code} da Casa dos Dados: {detalhe}")
        return None
    uuid = r.json().get("arquivo_uuid")
    if not uuid:
        log("❌ API não retornou identificador."); return None
    log(f"✅ Aceito. ID da solicitação: {uuid}")
    log("⏳ O arquivo está sendo gerado pela Casa dos Dados...")

    link = None
    for t in range(1, POLL_MAX + 1):
        try:
            rc = requests.get(f"{ENDPOINT_CONSULTAR}/{uuid}",
                              headers=_h(api_key), timeout=20)
            if rc.status_code == 200:
                link = rc.json().get("link")
                if link:
                    log("✅ Arquivo pronto!"); break
            elif rc.status_code == 404:
                log("❌ Solicitação não encontrada (404)."); return None
        except requests.exceptions.RequestException:
            pass
        espera = 4 if t <= 10 else (8 if t <= 40 else 12)
        if t % 5 == 0 or t <= 5:
            log(f"⏳ Processando... (verificação {t})")
        time.sleep(espera)
    if not link:
        log("⚠️ O arquivo ainda não ficou pronto a tempo, mas NÃO foi "
            "perdido nem o crédito desperdiçado.")
        log(f"➡️ Vá na aba 'Minhas solicitações' e baixe quando o "
            f"status estiver 'processado'. ID: {uuid}")
        return None

    log("⬇️ Baixando...")
    try:
        rd = requests.get(link, timeout=180); rd.raise_for_status()
    except requests.exceptions.RequestException as e:
        log(f"❌ Erro ao baixar: {e}"); return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "csv"
    ch = f"{nome}_{ts}"
    _ARQUIVOS[ch] = {
        "conteudo": rd.content, "filename": f"{ch}.{ext}",
        "mime": "text/csv",
        "criado": time.time(),
    }
    agora = time.time()
    for k in [k for k, v in _ARQUIVOS.items() if agora - v["criado"] > 3600]:
        _ARQUIVOS.pop(k, None)
    log(f"✅ Concluído! ({len(rd.content)/1024:.1f} KB)")
    return ch


@app.route("/")
def index():
    if not session.get("uid"):
        return Response(HTML_LOGIN, mimetype="text/html")
    return Response(HTML_APP, mimetype="text/html")


@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.json or {}
    u = db.autenticar(d.get("username", "").strip(), d.get("senha", ""))
    if not u:
        return jsonify({"ok": False, "msg": "Usuário ou senha incorretos."})
    session["uid"] = u["id"]
    session["username"] = u["username"]
    session["is_admin"] = u["is_admin"]
    return jsonify({"ok": True, "is_admin": u["is_admin"]})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/eu")
@login_obrigatorio
def api_eu():
    return jsonify({
        "ok": True, "username": session["username"],
        "is_admin": session["is_admin"],
        "tem_chave": bool(db.get_api_key()),
    })


@app.route("/api/admin/usuarios", methods=["GET"])
@admin_obrigatorio
def adm_listar():
    return jsonify({"ok": True, "usuarios": db.listar_usuarios()})


@app.route("/api/admin/usuarios", methods=["POST"])
@admin_obrigatorio
def adm_criar():
    d = request.json or {}
    ok, msg = db.criar_usuario(
        d.get("username", ""), d.get("senha", ""),
        bool(d.get("is_admin", False)))
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/admin/usuarios/<int:uid>", methods=["DELETE"])
@admin_obrigatorio
def adm_remover(uid):
    ok, msg = db.remover_usuario(uid)
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/admin/usuarios/<int:uid>/senha", methods=["POST"])
@admin_obrigatorio
def adm_senha(uid):
    ok, msg = db.alterar_senha(uid, (request.json or {}).get("senha", ""))
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/admin/apikey", methods=["GET"])
@admin_obrigatorio
def adm_get_key():
    k = db.get_api_key()
    mascarada = ("•" * 8 + k[-4:]) if k else ""
    return jsonify({"ok": True, "definida": bool(k), "preview": mascarada})


@app.route("/api/admin/apikey", methods=["POST"])
@admin_obrigatorio
def adm_set_key():
    nova = (request.json or {}).get("api_key", "").strip()
    if not nova:
        return jsonify({"ok": False, "msg": "Informe a chave."})
    db.set_api_key(nova)
    return jsonify({"ok": True, "msg": "Chave de API atualizada."})


@app.route("/api/saldo", methods=["POST"])
@login_obrigatorio
def api_saldo():
    key = db.get_api_key()
    if not key:
        return jsonify({"ok": False,
                        "msg": "Nenhuma chave configurada. Avise o admin."})
    try:
        r = requests.get(ENDPOINT_SALDO, headers=_h(key), timeout=20)
        if r.status_code == 200:
            return jsonify({"ok": True, "dados": r.json()})
        if r.status_code == 401:
            return jsonify({"ok": False, "msg": "Chave inválida (401)."})
        return jsonify({"ok": False, "msg": f"Erro (HTTP {r.status_code})."})
    except requests.exceptions.RequestException as e:
        return jsonify({"ok": False, "msg": f"Erro de conexão: {e}"})


# ---- NOVO: pré-visualização reaproveitando o modo teste (5 CNPJs) -------- #
@app.route("/api/previa", methods=["POST"])
@login_obrigatorio
def api_previa():
    """
    Mostra uma amostra de até 5 CNPJs na própria tela.
    Usado pelo Modo Teste — não gera arquivo, só consulta a amostra.
    Resolve o problema de download dependente da memória do servidor.
    """
    key = db.get_api_key()
    if not key:
        return jsonify({"ok": False,
                        "msg": "Nenhuma chave configurada. Avise o admin."})
    d = request.json or {}
    if not d.get("cnae", "").strip():
        return jsonify({"ok": False, "msg": "Informe ao menos um CNAE."})

    # Força limite de 5 para a prévia (mesmo custo do modo teste)
    d["total_linhas"] = 5
    pesquisa = montar_pesquisa(d)
    try:
        r = requests.post(ENDPOINT_PESQUISA, json=pesquisa,
                          headers=_h(key), timeout=30)
        if r.status_code == 401:
            return jsonify({"ok": False, "msg": "Chave inválida (401)."})
        if r.status_code == 403:
            return jsonify({"ok": False, "msg": "Sem saldo/permissão (403)."})
        if r.status_code not in (200, 201):
            try:
                det = r.json()
                det = (det.get("mensagem") or det.get("message")
                       or det.get("detail") or str(det))
            except Exception:
                det = (r.text or "")[:300]
            return jsonify({"ok": False,
                            "msg": f"HTTP {r.status_code}: {det}"})
        body = r.json()
        # A API pode devolver em 'cnpjs', 'data' ou 'empresas'
        registros = (body.get("cnpjs") or body.get("data")
                     or body.get("empresas") or [])
        amostra = []
        for e in registros[:5]:
            amostra.append({
                "cnpj": e.get("cnpj", ""),
                "razao_social": (e.get("razao_social")
                                 or e.get("nome", "")),
                "nome_fantasia": e.get("nome_fantasia", ""),
                "municipio": e.get("municipio", ""),
                "uf": e.get("uf", ""),
                "data_abertura": e.get("data_abertura", ""),
                "telefone": (e.get("telefone")
                             or e.get("telefone_1", "")),
                "email": e.get("email", ""),
            })
        total = (body.get("total") or body.get("quantidade")
                 or len(registros))
        return jsonify({"ok": True, "amostra": amostra, "total": total})
    except requests.exceptions.RequestException as e:
        return jsonify({"ok": False, "msg": f"Erro de conexão: {e}"})


@app.route("/api/captar", methods=["POST"])
@login_obrigatorio
def api_captar():
    key = db.get_api_key()
    if not key:
        return jsonify({"ok": False,
                        "msg": "Nenhuma chave configurada. Avise o admin."})
    d = request.json or {}
    if not d.get("cnae", "").strip():
        return jsonify({"ok": False, "msg": "Informe ao menos um CNAE."})
    msgs = []
    ch = gerar_e_baixar(
        api_key=key, nome=d.get("nome", "captacao_cnpj"),
        pesquisa=montar_pesquisa(d), tipo=d.get("tipo", "csv"),
        total_linhas=d.get("total_linhas", 0), log=msgs.append)
    return jsonify({"ok": bool(ch), "chave": ch, "log": msgs})


@app.route("/api/solicitacoes")
@login_obrigatorio
def api_solicitacoes():
    key = db.get_api_key()
    if not key:
        return jsonify({"ok": False, "msg": "Sem chave configurada."})
    try:
        r = requests.get(ENDPOINT_LISTAR, headers=_h(key), timeout=25)
        if r.status_code != 200:
            return jsonify({"ok": False,
                            "msg": f"Erro ao listar (HTTP {r.status_code})."})
        itens = r.json()
        if not isinstance(itens, list):
            itens = itens.get("data", []) if isinstance(itens, dict) else []
        out = []
        for it in itens[:40]:
            pq = it.get("pesquisa", {}) or {}
            out.append({
                "uuid": it.get("arquivo_uuid", ""),
                "nome": it.get("nome", ""),
                "status": it.get("status", ""),
                "quantidade": it.get("quantidade", 0),
                "criado": it.get("criado", ""),
                "cnae": ",".join(pq.get("codigo_atividade_principal", [])),
            })
        return jsonify({"ok": True, "itens": out})
    except requests.exceptions.RequestException as e:
        return jsonify({"ok": False, "msg": f"Erro de conexão: {e}"})


@app.route("/api/baixar-solicitacao/<uuid>")
@login_obrigatorio
def api_baixar_solicitacao(uuid):
    key = db.get_api_key()
    if not key:
        return "Sem chave configurada.", 400
    try:
        rc = requests.get(f"{ENDPOINT_CONSULTAR}/{uuid}",
                          headers=_h(key), timeout=20)
        if rc.status_code != 200:
            return ("O arquivo ainda não está pronto (status "
                    f"HTTP {rc.status_code}). Tente novamente em instantes."), 425
        link = rc.json().get("link")
        if not link:
            return "Arquivo ainda em processamento. Aguarde.", 425
        rd = requests.get(link, timeout=180)
        rd.raise_for_status()
        return send_file(
            io.BytesIO(rd.content), mimetype="text/csv",
            as_attachment=True,
            download_name=f"cnpjs_{uuid[:8]}.csv")
    except requests.exceptions.RequestException as e:
        return f"Erro ao baixar: {e}", 502


@app.route("/api/download/<chave>")
@login_obrigatorio
def api_download(chave):
    a = _ARQUIVOS.get(chave)
    if not a:
        return "Arquivo não encontrado ou expirado.", 404
    return send_file(io.BytesIO(a["conteudo"]), mimetype=a["mime"],
                     as_attachment=True, download_name=a["filename"])

# --------------------------------------------------------------------------- #
# Páginas HTML — MESMO design que está no ar (não alterar aparência)
# --------------------------------------------------------------------------- #
_BASE = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Outfit:wght@300;400;500;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
:root{
--bg:#0a0e14;--surface:#11161f;--surface2:#161d29;--line:#232c3b;
--txt:#e8edf4;--mut:#8b97a8;--accent:#d4ff3f;--accent2:#7c5cff;
--ok:#34d399;--err:#fb7185;--radius:14px}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--txt);
min-height:100vh;display:flex;justify-content:center;padding:40px 18px;
background-image:radial-gradient(circle at 15% 0%,rgba(124,92,255,.10),transparent 45%),radial-gradient(circle at 85% 100%,rgba(212,255,63,.07),transparent 45%);
background-attachment:fixed}
.card{background:var(--surface);border:1px solid var(--line);
border-radius:24px;padding:40px;width:100%;max-width:680px;
box-shadow:0 24px 70px rgba(0,0,0,.55);position:relative;
animation:rise .5s cubic-bezier(.2,.8,.2,1)}
@keyframes rise{from{opacity:0;transform:translateY(16px)}}
h1{font-family:'Fraunces',serif;font-size:30px;font-weight:600;
letter-spacing:-.5px;line-height:1.1}
h2{font-family:'Fraunces',serif;font-size:20px;font-weight:600;
margin:30px 0 6px}
.sub{color:var(--mut);font-size:14px;margin-top:6px;margin-bottom:8px}
.eyebrow{font-size:12px;letter-spacing:2.5px;text-transform:uppercase;
color:var(--accent);font-weight:600;margin-bottom:10px}
label{display:block;font-size:12.5px;font-weight:500;margin:18px 0 7px;
color:var(--mut);letter-spacing:.3px}
input[type=text],input[type=password],input[type=number],select{width:100%;
padding:13px 15px;border-radius:11px;border:1px solid var(--line);
background:var(--bg);color:var(--txt);font-size:14.5px;
font-family:'Outfit',sans-serif;transition:.18s}
input::placeholder{color:#56627a}
input:focus,select:focus{outline:none;border-color:var(--accent2);
box-shadow:0 0 0 4px rgba(124,92,255,.16)}
.row{display:flex;gap:14px;flex-wrap:wrap}.row>div{flex:1;min-width:140px}
.checks{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}
.chk{display:flex;align-items:center;gap:9px;cursor:pointer;
background:var(--bg);border:1px solid var(--line);padding:10px 14px;
border-radius:10px;font-size:13.5px;color:var(--mut);transition:.16s;
user-select:none}
.chk:hover{border-color:var(--accent2);color:var(--txt)}
.chk input{accent-color:var(--accent2);width:16px;height:16px}
.hint{font-size:12px;color:#5a657a;margin-top:6px;line-height:1.5}
button{width:100%;margin-top:26px;padding:15px;background:var(--accent);
color:#0a0e14;border:none;border-radius:12px;font-size:15px;
font-weight:600;font-family:'Outfit',sans-serif;cursor:pointer;
transition:.18s;letter-spacing:.2px}
button:hover{transform:translateY(-2px);
box-shadow:0 10px 26px rgba(212,255,63,.26)}
button:active{transform:translateY(0)}
button:disabled{background:#2a3342;color:#5a657a;transform:none;
box-shadow:none;cursor:not-allowed}
.btn-sec{background:transparent;color:var(--txt);
border:1px solid var(--line)}
.btn-sec:hover{border-color:var(--accent2);box-shadow:none;
background:rgba(124,92,255,.08)}
.btn-sm{width:auto;padding:9px 15px;font-size:13px;margin:0;
border-radius:9px}
.btn-ghost{background:transparent;color:var(--mut);
border:1px solid var(--line)}
.btn-ghost:hover{color:var(--txt);border-color:var(--accent2);
background:none;box-shadow:none;transform:none}
.btn-danger{background:transparent;color:var(--err);
border:1px solid rgba(251,113,133,.35)}
.btn-danger:hover{background:rgba(251,113,133,.12);box-shadow:none;
transform:none}
#log{margin-top:22px;background:var(--bg);border:1px solid var(--line);
border-radius:12px;padding:16px;font-size:12.5px;
font-family:'SF Mono',ui-monospace,monospace;max-height:240px;
overflow-y:auto;white-space:pre-wrap;display:none;line-height:1.7}
#log.show{display:block}
.box{background:var(--bg);border:1px solid var(--line);border-radius:11px;
padding:13px 15px;font-size:13px;margin-top:12px;display:none;
line-height:1.5}
.box.show{display:block;animation:rise .3s ease}
.dl{display:none;margin-top:16px}.dl.show{display:block;
animation:rise .35s ease}
a.dl-btn{display:flex;align-items:center;justify-content:center;gap:8px;
text-decoration:none;background:var(--ok);color:#04130d;padding:15px;
border-radius:12px;font-weight:600;transition:.18s}
a.dl-btn:hover{transform:translateY(-2px);
box-shadow:0 10px 26px rgba(52,211,153,.28)}
.topbar{display:flex;justify-content:space-between;align-items:flex-start;
gap:16px;margin-bottom:4px}
.tabs{display:flex;gap:8px;margin:26px 0 4px;border-bottom:1px solid
var(--line);padding-bottom:0}
.tab{padding:11px 4px;margin-right:22px;background:none;cursor:pointer;
font-size:14px;color:var(--mut);border-bottom:2px solid transparent;
transition:.16s;font-weight:500}
.tab:hover{color:var(--txt)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.painel{display:none}.painel.active{display:block;
animation:rise .35s ease}
table{width:100%;border-collapse:collapse;margin-top:14px;font-size:13px}
th{text-align:left;padding:10px 8px;color:var(--mut);font-weight:500;
font-size:12px;letter-spacing:.5px;text-transform:uppercase;
border-bottom:1px solid var(--line)}
td{text-align:left;padding:12px 8px;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:none}
.tag{font-size:11px;background:rgba(124,92,255,.18);color:#b9a8ff;
padding:3px 9px;border-radius:6px;font-weight:500}
.tag-m{background:rgba(139,151,168,.14);color:var(--mut)}
.linha-acoes{display:flex;gap:7px}
.divider{height:1px;background:var(--line);margin:28px 0}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:12px;
color:var(--mut);background:var(--bg);border:1px solid var(--line);
padding:5px 11px;border-radius:20px}
.dot{width:6px;height:6px;border-radius:50%;background:var(--ok)}
.dot.off{background:#5a657a}
.testbar{display:flex;align-items:center;gap:12px;background:var(--bg);
border:1px dashed var(--accent2);border-radius:12px;padding:14px 16px;
margin-top:20px}
.testbar .ic{font-size:20px}
.testbar div{flex:1}.testbar b{color:var(--txt);font-size:14px}
.testbar small{color:var(--mut);display:block;margin-top:2px}
.previa{margin-top:18px;display:none}
.previa.show{display:block;animation:rise .35s ease}
.previa-wrap{overflow-x:auto;border:1px solid var(--line);
border-radius:12px;background:var(--bg)}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-thumb{background:var(--line);border-radius:4px}
"""

HTML_LOGIN = """<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport"
content="width=device-width,initial-scale=1">
<title>Entrar — Captador de CNPJs</title><style>""" + _BASE + """
.card{max-width:420px}
.logo{width:46px;height:46px;border-radius:12px;
background:linear-gradient(135deg,var(--accent),#a8e024);
display:flex;align-items:center;justify-content:center;font-size:22px;
margin-bottom:22px}
</style></head><body><div class="card">
<div class="logo">◆</div>
<div class="eyebrow">Acesso restrito</div>
<h1>Captador de CNPJs</h1>
<div class="sub">Entre com suas credenciais da equipe</div>
<label>Usuário</label>
<input type="text" id="u" autofocus autocomplete="username">
<label>Senha</label>
<input type="password" id="s" autocomplete="current-password"
onkeydown="if(event.key==='Enter')entrar()">
<button onclick="entrar()">Entrar →</button>
<div class="box" id="erro"></div>
<script>
async function entrar(){
const e=document.getElementById('erro');
const r=await fetch('/api/login',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({username:document.getElementById('u').value,
senha:document.getElementById('s').value})});
const d=await r.json();
if(d.ok){location.reload();}
else{e.className='box show';e.style.color='var(--err)';
e.textContent='⚠ '+d.msg;}
}
</script></div></body></html>"""

HTML_APP = """<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport"
content="width=device-width,initial-scale=1">
<title>Captador de CNPJs</title><style>""" + _BASE + """</style>
</head><body><div class="card">
<div class="topbar">
<div>
<div class="eyebrow">Casa dos Dados</div>
<h1>Captador de CNPJs</h1>
</div>
<button class="btn-sm btn-ghost" onclick="sair()">Sair</button>
</div>
<div class="sub" id="ola"></div>

<div class="tabs">
<div class="tab active" id="t1" onclick="aba(1)">Captar</div>
<div class="tab" id="t3" onclick="aba(3)">Minhas solicitações</div>
<div class="tab" id="t2" onclick="aba(2)"
style="display:none">Administração</div>
</div>

<!-- ABA CAPTAR -->
<div class="painel active" id="p1">
<div class="box" id="avisochave"
style="display:none;color:var(--err)">
⚠ Nenhuma chave de API configurada. Avise o administrador.</div>

<div style="display:flex;align-items:center;gap:12px;margin-top:18px">
<span class="badge"><span class="dot" id="dotchave"></span>
<span id="statuschave">Verificando chave…</span></span>
<button class="btn-sm btn-sec" onclick="verSaldo()"
style="margin:0">Ver saldo</button>
</div>
<div class="box" id="saldo"></div>

<div class="testbar">
<span class="ic">🧪</span>
<div><b>Modo teste rápido</b>
<small>Marque para buscar só 5 CNPJs e ver a prévia na tela
gastando centavos.</small></div>
<label class="chk" style="margin:0">
<input type="checkbox" id="modo_teste" onchange="aplicarTeste()">
Ativar</label>
</div>

<label>CNAE(s) — separe por vírgula</label>
<input type="text" id="cnae" value="6920601"
placeholder="6920601, 6201500">
<div class="hint">6920601 = Atividades de contabilidade.
Use o código sem pontos ou traços.</div>

<div class="row">
<div><label>Situação cadastral</label>
<select id="situacao">
<option value="ATIVA">Ativa</option>
<option value="INAPTA">Inapta</option>
<option value="BAIXADA">Baixada</option>
<option value="SUSPENSA">Suspensa</option></select></div>
<div><label>Empresas novas — últimos X dias</label>
<input type="number" id="ultimos_dias" value="30" min="0">
<div class="hint">0 = sem filtro · 30 = recém-criadas</div></div>
</div>

<div class="row">
<div><label>Estado (UF) — separe por vírgula</label>
<input type="text" id="ufs" placeholder="SP, RJ"></div>
<div><label>Município — separe por vírgula</label>
<input type="text" id="municipios" placeholder="SAO PAULO"></div>
</div>

<div class="row">
<div><label>Formato do arquivo</label>
<select id="tipo">
<option value="csv">CSV (abre no Excel)</option></select>
<div class="hint">A Casa dos Dados gera apenas CSV. Ele abre
normalmente no Excel/Sheets.</div></div>
<div><label>Limite de linhas (0 = todas, máx 1000)</label>
<input type="number" id="total_linhas" value="0" min="0" max="1000">
<div class="hint">No modo teste vira 5 automaticamente</div></div>
</div>

<div class="checks">
<label class="chk"><input type="checkbox" id="com_telefone">
Só com telefone</label>
<label class="chk"><input type="checkbox" id="com_email">
Só com e-mail</label>
<label class="chk"><input type="checkbox" id="somente_mei">
Somente MEI</label>
</div>

<button id="btn" onclick="captar()">Gerar arquivo de CNPJs</button>

<!-- PRÉVIA: aparece no modo teste, mesmo visual do app -->
<div class="previa" id="previa">
<h2 style="margin-top:24px">Prévia (amostra de 5)</h2>
<div class="sub" id="previa_info"></div>
<div class="previa-wrap"><table id="previa_tab"></table></div>
</div>

<div id="log"></div><div class="dl" id="dl"></div>
</div>

<!-- ABA MINHAS SOLICITAÇÕES -->
<div class="painel" id="p3">
<h2>Minhas solicitações</h2>
<div class="sub">Arquivos que você já mandou gerar. Consultar
aqui <b>não gasta crédito</b>. Baixe quando o status for
"processado".</div>
<button class="btn-sm btn-sec" onclick="listarSolic()"
style="margin-top:6px">↻ Atualizar lista</button>
<div id="tabela_solic" style="margin-top:8px">
<div class="hint">Clique em "Atualizar lista" para carregar.</div>
</div>
</div>

<!-- ABA ADMIN -->
<div class="painel" id="p2">
<h2>Chave de API</h2>
<div class="sub" id="keyprev">Carregando…</div>
<label>Nova chave de API (Casa dos Dados)</label>
<input type="password" id="novachave"
placeholder="Cole aqui a chave obtida no portal">
<button class="btn-sm" style="margin-top:14px"
onclick="salvarChave()">Salvar chave</button>
<div class="box" id="msgchave"></div>

<div class="divider"></div>

<h2>Usuários da equipe</h2>
<div class="sub">Quem pode acessar este site</div>
<div id="tabela"></div>

<label>Adicionar novo usuário</label>
<div class="row">
<div><input type="text" id="nu" placeholder="nome de usuário"></div>
<div><input type="password" id="np" placeholder="senha"></div>
</div>
<label class="chk" style="margin-top:12px;width:fit-content">
<input type="checkbox" id="nadmin"> Conceder acesso de administrador
</label>
<button class="btn-sm" style="margin-top:14px"
onclick="criarUsuario()">Adicionar usuário</button>
<div class="box" id="msguser"></div>
</div>

<script>
const $=id=>document.getElementById(id);
let IS_ADMIN=false;

async function carregar(){
const r=await fetch('/api/eu');const d=await r.json();
if(!d.ok){location.reload();return;}
IS_ADMIN=d.is_admin;
$('ola').textContent='Conectado como '+d.username+
(d.is_admin?' · administrador':' · membro');
if(d.is_admin){$('t2').style.display='block';carregarAdmin();}
const dot=$('dotchave'),st=$('statuschave');
if(d.tem_chave){dot.className='dot';st.textContent='Chave configurada';}
else{dot.className='dot off';st.textContent='Sem chave';
$('avisochave').style.display='block';}
}
carregar();

function aba(n){
$('t1').classList.toggle('active',n===1);
$('t2').classList.toggle('active',n===2);
$('t3').classList.toggle('active',n===3);
$('p1').classList.toggle('active',n===1);
$('p2').classList.toggle('active',n===2);
$('p3').classList.toggle('active',n===3);
if(n===3) listarSolic();
}
async function listarSolic(){
const box=$('tabela_solic');
box.innerHTML='<div class="hint">Carregando…</div>';
try{
const r=await fetch('/api/solicitacoes');const d=await r.json();
if(!d.ok){box.innerHTML='<div class="box show" '+
'style="color:var(--err)">⚠ '+d.msg+'</div>';return;}
if(!d.itens.length){box.innerHTML='<div class="hint">'+
'Nenhuma solicitação encontrada ainda.</div>';return;}
let h='<table><tr><th>Nome</th><th>CNAE</th><th>Status</th>'+
'<th>Qtd</th><th></th></tr>';
d.itens.forEach(it=>{
const pronto=it.status==='processado';
const cor=pronto?'var(--ok)':'var(--mut)';
h+='<tr><td>'+(it.nome||'—')+'</td><td>'+(it.cnae||'—')+
'</td><td><span style="color:'+cor+'">'+
(it.status||'—')+'</span></td><td>'+(it.quantidade||0)+
'</td><td>'+(pronto
?'<a class="btn-sm" style="text-decoration:none;'+
'background:var(--ok);color:#04130d;padding:8px 13px;'+
'border-radius:8px" href="/api/baixar-solicitacao/'+
it.uuid+'">⬇ Baixar</a>'
:'<span class="hint">aguarde</span>')+'</td></tr>';
});
h+='</table>';box.innerHTML=h;
}catch(e){box.innerHTML='<div class="box show" '+
'style="color:var(--err)">⚠ Erro: '+e+'</div>';}
}
async function sair(){
await fetch('/api/logout',{method:'POST'});location.reload();
}
function aplicarTeste(){
const on=$('modo_teste').checked;
if(on){ $('total_linhas')._b=$('total_linhas').value;
$('total_linhas').value=5;$('total_linhas').disabled=true; }
else{ $('total_linhas').disabled=false;
$('total_linhas').value=$('total_linhas')._b||0;
$('previa').className='previa'; }
}
async function verSaldo(){
const b=$('saldo');b.className='box show';b.textContent='Consultando…';
const r=await fetch('/api/saldo',{method:'POST',
headers:{'Content-Type':'application/json'},body:'{}'});
const d=await r.json();
b.style.color=d.ok?'var(--txt)':'var(--err)';
b.textContent=d.ok?'💰 '+JSON.stringify(d.dados):'⚠ '+d.msg;
}
function corpoFiltros(){
return {cnae:$('cnae').value,situacao:$('situacao').value,
ufs:$('ufs').value,municipios:$('municipios').value,
ultimos_dias:$('ultimos_dias').value,tipo:$('tipo').value,
com_telefone:$('com_telefone').checked,
com_email:$('com_email').checked,
somente_mei:$('somente_mei').checked,
nome:'cnpj_'+$('cnae').value.split(',')[0].trim()};
}
async function captar(){
const log=$('log'),btn=$('btn'),dl=$('dl');
log.className='log show';log.textContent='▸ Iniciando…\\n';
dl.className='dl';dl.innerHTML='';

// MODO TESTE: mostra a prévia na tela (não depende de download)
if($('modo_teste').checked){
log.textContent='▸ Buscando prévia (5 CNPJs)…';
btn.disabled=true;btn.textContent='Buscando prévia…';
try{
const r=await fetch('/api/previa',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify(corpoFiltros())});
const d=await r.json();
if(d.ok){
renderPrevia(d.amostra,d.total);
log.textContent='▸ Prévia carregada: '+
d.amostra.length+' de '+d.total+' encontrados.';
}else{
log.textContent='✗ '+d.msg;
$('previa').className='previa';
}
}catch(e){log.textContent='✗ Erro: '+e;}
finally{btn.disabled=false;
btn.textContent='Gerar arquivo de CNPJs';}
return;
}

// MODO NORMAL: gera arquivo completo
const body=corpoFiltros();body.total_linhas=$('total_linhas').value;
btn.disabled=true;btn.textContent='Processando… pode levar minutos';
$('previa').className='previa';
try{
const r=await fetch('/api/captar',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify(body)});
const d=await r.json();
log.textContent=(d.log||[]).map(x=>'▸ '+x).join('\\n');
if(d.ok&&d.chave){dl.className='dl show';
dl.innerHTML='<a class="dl-btn" href="/api/download/'+d.chave+
'">⬇ Baixar arquivo</a>';}
else{
dl.className='dl show';
dl.innerHTML='<button onclick="aba(3)" style="margin:0;'+
'background:var(--accent2);color:#fff">Ver em Minhas '+
'solicitações →</button>';
if(!d.ok&&d.msg)log.textContent+='\\n✗ '+d.msg;
}
}catch(e){log.textContent+='\\n✗ Erro: '+e;}
finally{btn.disabled=false;
btn.textContent='Gerar arquivo de CNPJs';}
}
function renderPrevia(amostra,total){
const p=$('previa'),tab=$('previa_tab'),info=$('previa_info');
if(!amostra||!amostra.length){
info.textContent='Nenhum resultado com esses filtros.';
tab.innerHTML='';p.className='previa show';return;
}
info.textContent='Mostrando '+amostra.length+
' de '+total+' empresas encontradas. '+
'Desative o Modo Teste e gere o arquivo para baixar todos.';
let h='<tr><th>Razão social</th><th>CNPJ</th>'+
'<th>Município/UF</th><th>Abertura</th>'+
'<th>Telefone</th><th>E-mail</th></tr>';
amostra.forEach(e=>{
h+='<tr><td>'+(e.razao_social||e.nome_fantasia||'—')+
'</td><td>'+(e.cnpj||'—')+'</td><td>'+
(e.municipio||'—')+'/'+(e.uf||'—')+'</td><td>'+
(e.data_abertura||'—')+'</td><td>'+(e.telefone||'—')+
'</td><td>'+(e.email||'—')+'</td></tr>';
});
tab.innerHTML=h;p.className='previa show';
}
async function carregarAdmin(){
const r=await fetch('/api/admin/apikey');const d=await r.json();
$('keyprev').textContent=d.definida
?('Chave atual: '+d.preview):'Nenhuma chave configurada ainda.';
listarUsuarios();
}
async function salvarChave(){
const m=$('msgchave');
const r=await fetch('/api/admin/apikey',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({api_key:$('novachave').value})});
const d=await r.json();
m.className='box show';m.style.color=d.ok?'var(--ok)':'var(--err)';
m.textContent=(d.ok?'✓ ':'⚠ ')+d.msg;
if(d.ok){$('novachave').value='';
$('avisochave').style.display='none';carregar();carregarAdmin();}
}
async function listarUsuarios(){
const r=await fetch('/api/admin/usuarios');const d=await r.json();
if(!d.ok)return;
let h='<table><tr><th>Usuário</th><th>Tipo</th><th>Criado</th>'+
'<th></th></tr>';
d.usuarios.forEach(u=>{
h+='<tr><td>'+u.username+'</td><td>'+(u.is_admin
?'<span class=tag>admin</span>'
:'<span class="tag tag-m">membro</span>')+'</td><td>'+
(u.criado_em||'').split(' ')[0]+'</td><td><div class=linha-acoes>'+
'<button class="btn-sm btn-sec" onclick="resetSenha('+u.id+
')">Senha</button><button class="btn-sm btn-danger" onclick='+
'"remover('+u.id+',\\''+u.username+'\\')">Remover</button>'+
'</div></td></tr>';});
h+='</table>';$('tabela').innerHTML=h;
}
async function criarUsuario(){
const m=$('msguser');
const r=await fetch('/api/admin/usuarios',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({username:$('nu').value,senha:$('np').value,
is_admin:$('nadmin').checked})});
const d=await r.json();
m.className='box show';m.style.color=d.ok?'var(--ok)':'var(--err)';
m.textContent=(d.ok?'✓ ':'⚠ ')+d.msg;
if(d.ok){$('nu').value='';$('np').value='';
$('nadmin').checked=false;listarUsuarios();}
}
async function remover(id,nome){
if(!confirm('Remover o usuário "'+nome+'"?'))return;
const r=await fetch('/api/admin/usuarios/'+id,{method:'DELETE'});
const d=await r.json();if(!d.ok)alert(d.msg);listarUsuarios();
}
async function resetSenha(id){
const nova=prompt('Nova senha para este usuário:');
if(!nova)return;
const r=await fetch('/api/admin/usuarios/'+id+'/senha',
{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({senha:nova})});
const d=await r.json();alert(d.msg);
}
</script>
</div></body></html>"""


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    import webbrowser, threading
    if porta == 5000:
        threading.Thread(
            target=lambda: (time.sleep(1.2),
                            webbrowser.open("http://localhost:5000")),
            daemon=True).start()
    app.run(host="0.0.0.0", port=porta, debug=False)
