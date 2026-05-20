"""
Captador de CNPJs — Casa dos Dados v5
VERSÃO CORRIGIDA PARA RENDER
"""

import os
import secrets
import sqlite3
from functools import wraps

import requests
from flask import (
    Flask,
    jsonify,
    request,
    Response,
    session,
    redirect
)

# =========================================================
# CONFIG
# =========================================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DB_PATH = "database.db"

ENDPOINT_GERAR = "https://api.casadosdados.com.br/v5/cnpj/pesquisa/arquivo"
ENDPOINT_CONSULTAR = "https://api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo"
ENDPOINT_LISTAR = "https://api.casadosdados.com.br/v4/cnpj/pesquisa/arquivo"
ENDPOINT_PESQUISA = "https://api.casadosdados.com.br/v5/cnpj/pesquisa"
ENDPOINT_SALDO = "https://api.casadosdados.com.br/v5/saldo"


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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        senha TEXT,
        is_admin INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS config (
        chave TEXT PRIMARY KEY,
        valor TEXT
    )
    """)

    admin = cur.execute(
        "SELECT * FROM usuarios WHERE username='admin'"
    ).fetchone()

    if not admin:
        cur.execute("""
        INSERT INTO usuarios(username, senha, is_admin)
        VALUES('admin', 'admin123', 1)
        """)

    c.commit()
    c.close()


init_db()


# =========================================================
# HELPERS
# =========================================================

def auth(username, senha):
    c = conn()

    cur = c.cursor()

    cur.execute("""
    SELECT id, username, is_admin
    FROM usuarios
    WHERE username=? AND senha=?
    """, (username, senha))

    r = cur.fetchone()

    c.close()

    if not r:
        return None

    return {
        "id": r[0],
        "username": r[1],
        "is_admin": bool(r[2])
    }


def get_api_key():
    c = conn()

    cur = c.cursor()

    cur.execute("""
    SELECT valor
    FROM config
    WHERE chave='api_key'
    """)

    r = cur.fetchone()

    c.close()

    return r[0] if r else None


def set_api_key(v):
    c = conn()

    cur = c.cursor()

    cur.execute("""
    INSERT OR REPLACE INTO config(chave, valor)
    VALUES('api_key', ?)
    """, (v,))

    c.commit()
    c.close()


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("uid"):
            return jsonify({
                "ok": False,
                "msg": "Faça login"
            }), 401

        return f(*a, **k)

    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("is_admin"):
            return jsonify({
                "ok": False,
                "msg": "Admin apenas"
            }), 403

        return f(*a, **k)

    return w


def headers(key):
    return {
        "api-key": key,
        "Content-Type": "application/json"
    }


# =========================================================
# HTML
# =========================================================

HTML_LOGIN = """
<!DOCTYPE html>
<html lang="pt-br">

<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login</title>

<link rel="icon" href="data:,">

<style>

body{
background:#0f172a;
color:white;
font-family:Arial;
display:flex;
justify-content:center;
align-items:center;
height:100vh;
margin:0;
}

.box{
background:#111827;
padding:40px;
border-radius:12px;
width:320px;
}

input{
width:100%;
padding:12px;
margin-top:10px;
border:none;
border-radius:8px;
background:#1f2937;
color:white;
}

button{
width:100%;
padding:12px;
margin-top:16px;
border:none;
border-radius:8px;
background:#84cc16;
font-weight:bold;
cursor:pointer;
}

#erro{
margin-top:12px;
color:#fb7185;
}

</style>
</head>

<body>

<div class="box">

<h2>Captador CNPJ</h2>

<input id="u" placeholder="Usuário">
<input id="s" type="password" placeholder="Senha">

<button onclick="entrar()">
Entrar
</button>

<div id="erro"></div>

</div>

<script>

async function entrar(){

const r = await fetch('/api/login',{
method:'POST',
headers:{
'Content-Type':'application/json'
},
body:JSON.stringify({
username:document.getElementById('u').value,
senha:document.getElementById('s').value
})
});

const d = await r.json();

if(d.ok){
location.reload();
}else{
document.getElementById('erro').innerText=d.msg;
}

}

</script>

</body>
</html>
"""

HTML_APP = """
<!DOCTYPE html>
<html lang="pt-br">

<head>

<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>Captador</title>

<link rel="icon" href="data:,">

<style>

body{
background:#0f172a;
color:white;
font-family:Arial;
margin:0;
padding:30px;
}

.box{
max-width:900px;
margin:auto;
background:#111827;
padding:30px;
border-radius:12px;
}

input{
width:100%;
padding:12px;
margin-top:10px;
border:none;
border-radius:8px;
background:#1f2937;
color:white;
}

button{
padding:12px 18px;
border:none;
border-radius:8px;
background:#84cc16;
font-weight:bold;
cursor:pointer;
margin-top:14px;
}

table{
width:100%;
margin-top:20px;
border-collapse:collapse;
}

td,th{
border:1px solid #374151;
padding:10px;
}

#log{
margin-top:20px;
white-space:pre-wrap;
background:#0b1220;
padding:16px;
border-radius:8px;
display:none;
}

#log.show{
display:block;
}

</style>

</head>

<body>

<div class="box">

<h1>Captador de CNPJs</h1>

<button onclick="logout()">
Sair
</button>

<hr>

<h3>CNAE</h3>

<input id="cnae" value="6920601">

<button onclick="previa()">
Modo Teste
</button>

<button onclick="captar()">
Gerar Arquivo
</button>

<div id="log"></div>

<div id="previa"></div>

</div>

<script>

function showLog(txt){

const log = document.getElementById('log');

log.classList.add('show');

log.innerText = txt;

}

async function logout(){

await fetch('/api/logout',{
method:'POST'
});

location.reload();

}

async function previa(){

showLog('Buscando prévia...');

const r = await fetch('/api/previa',{
method:'POST',
headers:{
'Content-Type':'application/json'
},
body:JSON.stringify({
cnae:document.getElementById('cnae').value
})
});

const d = await r.json();

if(!d.ok){
showLog(d.msg);
return;
}

let h = `
<table>
<tr>
<th>CNPJ</th>
<th>Razão Social</th>
</tr>
`;

d.amostra.forEach(e=>{

h += `
<tr>
<td>${e.cnpj || ''}</td>
<td>${e.razao_social || ''}</td>
</tr>
`;

});

h += "</table>";

document.getElementById('previa').innerHTML = h;

showLog('Prévia carregada');

}

async function captar(){

showLog('Gerando solicitação...');

const r = await fetch('/api/captar',{
method:'POST',
headers:{
'Content-Type':'application/json'
},
body:JSON.stringify({
cnae:document.getElementById('cnae').value
})
});

const d = await r.json();

if(!d.ok){
showLog(d.msg);
return;
}

showLog('Solicitação enviada com sucesso');

}

</script>

</body>
</html>
"""


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def index():

    if not session.get("uid"):

        return Response(
            HTML_LOGIN,
            content_type="text/html; charset=utf-8"
        )

    return Response(
        HTML_APP,
        content_type="text/html; charset=utf-8"
    )


@app.route("/api/login", methods=["POST"])
def api_login():

    d = request.json or {}

    u = auth(
        d.get("username", ""),
        d.get("senha", "")
    )

    if not u:
        return jsonify({
            "ok": False,
            "msg": "Usuário inválido"
        })

    session["uid"] = u["id"]
    session["username"] = u["username"]
    session["is_admin"] = u["is_admin"]

    return jsonify({
        "ok": True
    })


@app.route("/api/logout", methods=["POST"])
def api_logout():

    session.clear()

    return jsonify({
        "ok": True
    })


@app.route("/api/previa", methods=["POST"])
@login_required
def api_previa():

    key = get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "Configure a API KEY"
        })

    d = request.json or {}

    pesquisa = {
        "codigo_atividade_principal": [
            x.strip()
            for x in d.get("cnae", "").split(",")
            if x.strip()
        ],
        "limite": 5
    }

    try:

        r = requests.post(
            ENDPOINT_PESQUISA,
            json=pesquisa,
            headers=headers(key),
            timeout=30
        )

        if r.status_code != 200:

            return jsonify({
                "ok": False,
                "msg": f"Erro HTTP {r.status_code}"
            })

        body = r.json()

        registros = (
            body.get("cnpjs")
            or body.get("data")
            or []
        )

        amostra = []

        for e in registros[:5]:

            amostra.append({
                "cnpj": e.get("cnpj"),
                "razao_social": e.get("razao_social")
            })

        return jsonify({
            "ok": True,
            "amostra": amostra
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "msg": str(e)
        })


@app.route("/api/captar", methods=["POST"])
@login_required
def api_captar():

    key = get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "Configure API KEY"
        })

    d = request.json or {}

    payload = {
        "nome": "captacao",
        "tipo": "csv",
        "pesquisa": {
            "codigo_atividade_principal": [
                x.strip()
                for x in d.get("cnae", "").split(",")
                if x.strip()
            ]
        }
    }

    try:

        r = requests.post(
            ENDPOINT_GERAR,
            json=payload,
            headers=headers(key),
            timeout=30
        )

        if r.status_code not in [200, 201, 202]:

            return jsonify({
                "ok": False,
                "msg": f"Erro HTTP {r.status_code}"
            })

        return jsonify({
            "ok": True
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "msg": str(e)
        })


@app.route("/api/admin/apikey", methods=["POST"])
@login_required
@admin_required
def api_admin_apikey():

    d = request.json or {}

    key = d.get("api_key", "").strip()

    if not key:

        return jsonify({
            "ok": False,
            "msg": "Informe a chave"
        })

    set_api_key(key)

    return jsonify({
        "ok": True
    })


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )import io
import os
import time
import secrets
from functools import wraps

import requests
from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    Response,
    session,
    redirect
)

# =========================================================
# APP
# =========================================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# =========================================================
# CONFIG API
# =========================================================

ENDPOINT_GERAR = "https://api.casadosdados.com.br/v5/cnpj/pesquisa/arquivo"
ENDPOINT_CONSULTAR = "https://api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo"
ENDPOINT_LISTAR = "https://api.casadosdados.com.br/v4/cnpj/pesquisa/arquivo"
ENDPOINT_PESQUISA = "https://api.casadosdados.com.br/v5/cnpj/pesquisa"
ENDPOINT_SALDO = "https://api.casadosdados.com.br/v5/saldo"

# =========================================================
# BANCO LOCAL SIMPLES
# =========================================================

USUARIOS = [
    {
        "id": 1,
        "username": "admin",
        "senha": "admin123",
        "is_admin": True
    }
]

API_KEY = os.environ.get("API_KEY", "")

_ARQUIVOS = {}

# =========================================================
# HELPERS
# =========================================================

def autenticar(username, senha):
    for u in USUARIOS:
        if (
            u["username"] == username
            and u["senha"] == senha
        ):
            return u

    return None


def login_obrigatorio(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("uid"):
            return jsonify({
                "ok": False,
                "msg": "Faça login."
            }), 401

        return f(*a, **k)

    return w


def admin_obrigatorio(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("is_admin"):
            return jsonify({
                "ok": False,
                "msg": "Acesso restrito ao admin."
            }), 403

        return f(*a, **k)

    return w


def _h(key):
    return {
        "api-key": key,
        "Content-Type": "application/json"
    }


def get_api_key():
    global API_KEY
    return API_KEY


def set_api_key(v):
    global API_KEY
    API_KEY = v


def montar_pesquisa(d):
    p = {
        "codigo_atividade_principal": [
            c.strip()
            for c in d.get("cnae", "").split(",")
            if c.strip()
        ],
        "situacao_cadastral": [
            d.get("situacao") or "ATIVA"
        ]
    }

    if d.get("ufs"):
        p["uf"] = [
            u.strip().lower()
            for u in d["ufs"].split(",")
            if u.strip()
        ]

    if d.get("municipios"):
        p["municipio"] = [
            m.strip().lower()
            for m in d["municipios"].split(",")
            if m.strip()
        ]

    if d.get("ultimos_dias"):
        try:
            dias = int(d["ultimos_dias"])

            if dias > 0:
                p["data_abertura"] = {
                    "ultimos_dias": dias
                }

        except Exception:
            pass

    if d.get("somente_mei"):
        p["mei"] = {
            "optante": True
        }

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


def disparar_solicitacao(api_key, nome, pesquisa, log):
    payload = {
        "total_linhas": 0,
        "nome": nome,
        "tipo": "csv",
        "pesquisa": pesquisa
    }

    log("📤 Enviando solicitação para Casa dos Dados...")

    try:
        r = requests.post(
            ENDPOINT_GERAR,
            json=payload,
            headers=_h(api_key),
            timeout=30
        )

    except requests.exceptions.RequestException as e:
        log(f"❌ Erro conexão: {e}")
        return None

    if r.status_code not in (200, 201, 202):
        log(f"❌ HTTP {r.status_code}")
        return None

    try:
        body = r.json()

    except Exception:
        log("❌ Erro JSON")
        return None

    uuid = body.get("arquivo_uuid")

    if not uuid:
        log("❌ API não retornou UUID")
        return None

    log(f"✅ Solicitação criada: {uuid}")

    return uuid

# =========================================================
# INDEX
# =========================================================

@app.route("/")
def index():
    return Response(
        """
        <h1>Servidor funcionando</h1>
        <p>Captador CNPJ online</p>
        """,
        mimetype="text/html"
    )


@app.route("/favicon.ico")
def favicon():
    return "", 204

# =========================================================
# LOGIN
# =========================================================

@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.json or {}

    u = autenticar(
        d.get("username", "").strip(),
        d.get("senha", "")
    )

    if not u:
        return jsonify({
            "ok": False,
            "msg": "Usuário ou senha incorretos."
        })

    session["uid"] = u["id"]
    session["username"] = u["username"]
    session["is_admin"] = u["is_admin"]

    return jsonify({
        "ok": True,
        "is_admin": u["is_admin"]
    })


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()

    return jsonify({
        "ok": True
    })


@app.route("/api/eu")
@login_obrigatorio
def api_eu():
    return jsonify({
        "ok": True,
        "username": session["username"],
        "is_admin": session["is_admin"]
    })

# =========================================================
# ADMIN
# =========================================================

@app.route("/api/admin/usuarios")
@admin_obrigatorio
def admin_usuarios():
    return jsonify({
        "ok": True,
        "usuarios": USUARIOS
    })


@app.route("/api/admin/apikey", methods=["GET"])
@admin_obrigatorio
def admin_get_key():
    k = get_api_key()

    return jsonify({
        "ok": True,
        "api_key": k
    })


@app.route("/api/admin/apikey", methods=["POST"])
@admin_obrigatorio
def admin_set_key():
    d = request.json or {}

    set_api_key(
        d.get("api_key", "").strip()
    )

    return jsonify({
        "ok": True,
        "msg": "API KEY atualizada"
    })

# =========================================================
# SALDO
# =========================================================

@app.route("/api/saldo", methods=["POST"])
@login_obrigatorio
def api_saldo():
    key = get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "API KEY não configurada."
        })

    try:
        r = requests.get(
            ENDPOINT_SALDO,
            headers=_h(key),
            timeout=20
        )

        return jsonify({
            "ok": r.status_code == 200,
            "status": r.status_code,
            "dados": r.json()
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "msg": str(e)
        })

# =========================================================
# PRÉVIA
# =========================================================

@app.route("/api/previa", methods=["POST"])
@login_obrigatorio
def api_previa():
    key = get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "Configure API KEY."
        })

    d = request.json or {}

    pesquisa = montar_pesquisa(d)

    try:
        r = requests.post(
            ENDPOINT_PESQUISA,
            json=pesquisa,
            headers=_h(key),
            timeout=30
        )

        return jsonify({
            "ok": r.status_code == 200,
            "dados": r.json()
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "msg": str(e)
        })

# =========================================================
# CAPTAR
# =========================================================

@app.route("/api/captar", methods=["POST"])
@login_obrigatorio
def api_captar():
    key = get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "Configure API KEY."
        })

    d = request.json or {}

    msgs = []

    uuid = disparar_solicitacao(
        api_key=key,
        nome=d.get("nome", "captacao"),
        pesquisa=montar_pesquisa(d),
        log=msgs.append
    )

    return jsonify({
        "ok": bool(uuid),
        "uuid": uuid,
        "log": msgs
    })

# =========================================================
# SOLICITAÇÕES
# =========================================================

@app.route("/api/solicitacoes")
@login_obrigatorio
def api_solicitacoes():
    key = get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "Configure API KEY."
        })

    try:
        r = requests.get(
            ENDPOINT_LISTAR,
            headers=_h(key),
            timeout=25
        )

        return jsonify({
            "ok": r.status_code == 200,
            "dados": r.json()
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "msg": str(e)
        })

# =========================================================
# BAIXAR
# =========================================================

@app.route("/api/baixar-solicitacao/<uuid>")
@login_obrigatorio
def baixar(uuid):
    key = get_api_key()

    if not key:
        return "Sem API KEY", 400

    try:
        r = requests.get(
            f"{ENDPOINT_CONSULTAR}/{uuid}",
            headers=_h(key),
            timeout=30
        )

        if r.status_code != 200:
            return "Arquivo não pronto", 425

        body = r.json()

        link = body.get("link")

        if not link:
            return "Arquivo processando", 425

        return redirect(link)

    except Exception as e:
        return str(e), 500

# =========================================================
# DOWNLOAD LOCAL
# =========================================================

@app.route("/api/download/<chave>")
@login_obrigatorio
def api_download(chave):
    a = _ARQUIVOS.get(chave)

    if not a:
        return "Arquivo não encontrado.", 404

    return send_file(
        io.BytesIO(a["conteudo"]),
        mimetype=a["mime"],
        as_attachment=True,
        download_name=a["filename"]
    )

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=porta,
        debug=False
    )
