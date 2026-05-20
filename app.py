import io
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
