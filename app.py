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

import db

# =========================================================
# CONFIG
# =========================================================

ENDPOINT_GERAR = "https://api.casadosdados.com.br/v5/cnpj/pesquisa/arquivo"
ENDPOINT_CONSULTAR = "https://api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo"
ENDPOINT_LISTAR = "https://api.casadosdados.com.br/v4/cnpj/pesquisa/arquivo"
ENDPOINT_PESQUISA = "https://api.casadosdados.com.br/v5/cnpj/pesquisa"
ENDPOINT_SALDO = "https://api.casadosdados.com.br/v5/saldo"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

db.init_db()

_ARQUIVOS = {}


# =========================================================
# HELPERS
# =========================================================

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

        except:
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

    except:
        pass

    return p


def disparar_solicitacao(api_key, nome, pesquisa, log):
    payload = {
        "total_linhas": 0,
        "nome": nome,
        "tipo": "csv",
        "pesquisa": pesquisa
    }

    log("📤 Enviando solicitação para a Casa dos Dados...")

    try:
        r = requests.post(
            ENDPOINT_GERAR,
            json=payload,
            headers=_h(api_key),
            timeout=30
        )

    except requests.exceptions.RequestException as e:
        log(f"❌ Erro de conexão: {e}")
        return None

    if r.status_code == 401:
        log("❌ Chave inválida (401)")
        return None

    if r.status_code == 403:
        log("❌ Sem saldo/permissão (403)")
        return None

    if r.status_code not in (200, 201, 202):
        try:
            detalhe = r.json()

            detalhe = (
                detalhe.get("mensagem")
                or detalhe.get("message")
                or detalhe.get("detail")
                or str(detalhe)
            )

        except:
            detalhe = r.text[:300]

        log(f"❌ HTTP {r.status_code}: {detalhe}")
        return None

    uuid = r.json().get("arquivo_uuid")

    if not uuid:
        log("❌ API não retornou identificador.")
        return None

    log(f"✅ Solicitação aceita! ID: {uuid}")

    return uuid


# =========================================================
# ROTAS
# =========================================================

@app.route("/")
def index():
    return Response(
        "<h1>Servidor funcionando</h1>",
        mimetype="text/html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.json or {}

    u = db.autenticar(
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
        "is_admin": session["is_admin"],
        "tem_chave": bool(db.get_api_key())
    })


# =========================================================
# ADMIN
# =========================================================

@app.route("/api/admin/usuarios", methods=["GET"])
@admin_obrigatorio
def adm_listar():
    return jsonify({
        "ok": True,
        "usuarios": db.listar_usuarios()
    })


@app.route("/api/admin/usuarios", methods=["POST"])
@admin_obrigatorio
def adm_criar():
    d = request.json or {}

    ok, msg = db.criar_usuario(
        d.get("username", ""),
        d.get("senha", ""),
        bool(d.get("is_admin", False))
    )

    return jsonify({
        "ok": ok,
        "msg": msg
    })


@app.route("/api/admin/usuarios/<int:uid>", methods=["DELETE"])
@admin_obrigatorio
def adm_remover(uid):
    ok, msg = db.remover_usuario(uid)

    return jsonify({
        "ok": ok,
        "msg": msg
    })


@app.route("/api/admin/usuarios/<int:uid>/senha", methods=["POST"])
@admin_obrigatorio
def adm_senha(uid):
    ok, msg = db.alterar_senha(
        uid,
        (request.json or {}).get("senha", "")
    )

    return jsonify({
        "ok": ok,
        "msg": msg
    })


@app.route("/api/admin/apikey", methods=["GET"])
@admin_obrigatorio
def adm_get_key():
    k = db.get_api_key()

    mascarada = ("•" * 8 + k[-4:]) if k else ""

    return jsonify({
        "ok": True,
        "definida": bool(k),
        "preview": mascarada
    })


@app.route("/api/admin/apikey", methods=["POST"])
@admin_obrigatorio
def adm_set_key():
    nova = (request.json or {}).get("api_key", "").strip()

    if not nova:
        return jsonify({
            "ok": False,
            "msg": "Informe a chave."
        })

    db.set_api_key(nova)

    return jsonify({
        "ok": True,
        "msg": "Chave atualizada."
    })


# =========================================================
# SALDO
# =========================================================

@app.route("/api/saldo", methods=["POST"])
@login_obrigatorio
def api_saldo():
    key = db.get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "Nenhuma chave configurada."
        })

    try:
        r = requests.get(
            ENDPOINT_SALDO,
            headers=_h(key),
            timeout=20
        )

        if r.status_code == 200:
            return jsonify({
                "ok": True,
                "dados": r.json()
            })

        if r.status_code == 401:
            return jsonify({
                "ok": False,
                "msg": "Chave inválida."
            })

        if r.status_code == 403:
            return jsonify({
                "ok": False,
                "msg": "Sem saldo."
            })

        return jsonify({
            "ok": False,
            "msg": f"Erro HTTP {r.status_code}"
        })

    except requests.exceptions.RequestException as e:
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
    key = db.get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "Nenhuma chave configurada."
        })

    d = request.json or {}

    if not d.get("cnae", "").strip():
        return jsonify({
            "ok": False,
            "msg": "Informe um CNAE."
        })

    d["total_linhas"] = 5

    pesquisa = montar_pesquisa(d)

    try:
        r = requests.post(
            ENDPOINT_PESQUISA,
            json=pesquisa,
            headers=_h(key),
            timeout=30
        )

        if r.status_code not in (200, 201):
            return jsonify({
                "ok": False,
                "msg": f"HTTP {r.status_code}"
            })

        body = r.json()

        registros = (
            body.get("cnpjs")
            or body.get("data")
            or body.get("empresas")
            or []
        )

        amostra = []

        for e in registros[:5]:
            amostra.append({
                "cnpj": e.get("cnpj", ""),
                "razao_social": e.get("razao_social", ""),
                "municipio": e.get("municipio", ""),
                "uf": e.get("uf", ""),
                "telefone": e.get("telefone", ""),
                "email": e.get("email", "")
            })

        return jsonify({
            "ok": True,
            "amostra": amostra,
            "total": len(registros)
        })

    except requests.exceptions.RequestException as e:
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
    key = db.get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "Nenhuma chave configurada."
        })

    d = request.json or {}

    if not d.get("cnae", "").strip():
        return jsonify({
            "ok": False,
            "msg": "Informe um CNAE."
        })

    msgs = []

    uuid = disparar_solicitacao(
        api_key=key,
        nome=d.get("nome", "captacao_cnpj"),
        pesquisa=montar_pesquisa(d),
        log=msgs.append
    )

    return jsonify({
        "ok": bool(uuid),
        "uuid": uuid,
        "log": msgs
    })


# =========================================================
# LISTAR SOLICITAÇÕES
# =========================================================

@app.route("/api/solicitacoes")
@login_obrigatorio
def api_solicitacoes():
    key = db.get_api_key()

    if not key:
        return jsonify({
            "ok": False,
            "msg": "Sem chave."
        })

    try:
        r = requests.get(
            ENDPOINT_LISTAR,
            headers=_h(key),
            timeout=25
        )

        if r.status_code != 200:
            return jsonify({
                "ok": False,
                "msg": f"HTTP {r.status_code}"
            })

        itens = r.json()

        if not isinstance(itens, list):
            itens = itens.get("data", [])

        out = []

        for it in itens[:40]:
            pq = it.get("pesquisa", {}) or {}

            out.append({
                "uuid": it.get("arquivo_uuid", ""),
                "nome": it.get("nome", ""),
                "status": it.get("status", ""),
                "quantidade": it.get("quantidade", 0),
                "cnae": ",".join(
                    pq.get("codigo_atividade_principal", [])
                )
            })

        return jsonify({
            "ok": True,
            "itens": out
        })

    except requests.exceptions.RequestException as e:
        return jsonify({
            "ok": False,
            "msg": str(e)
        })


# =========================================================
# BAIXAR
# =========================================================

@app.route("/api/baixar-solicitacao/<uuid>")
@login_obrigatorio
def api_baixar_solicitacao(uuid):
    key = db.get_api_key()

    if not key:
        return "Sem chave configurada.", 400

    try:
        rc = requests.get(
            f"{ENDPOINT_CONSULTAR}/{uuid}",
            headers=_h(key),
            timeout=30
        )

        if rc.status_code != 200:
            return (
                "Arquivo ainda não pronto. "
                f"(HTTP {rc.status_code})"
            ), 425

        try:
            dados = rc.json()

        except Exception as e:
            return f"Erro ao processar JSON: {e}", 502

        link = dados.get("link")

        if not link:
            return "Arquivo ainda processando.", 425

        return redirect(link)

    except requests.exceptions.RequestException as e:
        return f"Erro: {e}", 502


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

    import webbrowser
    import threading

    if porta == 5000:
        threading.Thread(
            target=lambda: (
                time.sleep(1.2),
                webbrowser.open("http://localhost:5000")
            ),
            daemon=True
        ).start()

    app.run(
        host="0.0.0.0",
        port=porta,
        debug=False
    )
