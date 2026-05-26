"""
Camada de dados — Postgres (produção) ou SQLite (local)
========================================================

Detecção automática:
  - Se existir a variável de ambiente DATABASE_URL  -> usa Postgres
    (é o que o Render fornece ao criar um banco Postgres grátis).
    Os dados ficam PERMANENTES — não somem ao reiniciar/hibernar.
  - Caso contrário -> usa SQLite local (arquivo captador.db),
    bom para rodar e testar no seu PC.

A interface pública é idêntica nos dois modos — o app.py não muda.
Segurança: senhas com hash PBKDF2 (sem dependência externa).
"""

import os
import hashlib
import secrets
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_SENHA_INICIAL = os.environ.get("ADMIN_SENHA", "admin123")

if USE_PG:
    import psycopg
    from psycopg.rows import dict_row
    _DSN = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    import sqlite3
    DB_PATH = os.environ.get("DATABASE_PATH", "captador.db")


def hash_senha(senha: str, salt: str = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 100_000)
    return f"{salt}${dk.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        salt, _ = armazenado.split("$", 1)
    except (ValueError, AttributeError):
        return False
    return secrets.compare_digest(hash_senha(senha, salt), armazenado)


@contextmanager
def get_db():
    if USE_PG:
        conn = psycopg.connect(_DSN, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _q(sql: str) -> str:
    return sql.replace("?", "%s") if USE_PG else sql


def _exec(c, sql, params=()):
    cur = c.cursor()
    cur.execute(_q(sql), params)
    return cur


def init_db():
    """Cria as tabelas e garante que sempre exista um admin."""
    with get_db() as c:
        if USE_PG:
            _exec(c, """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id        SERIAL PRIMARY KEY,
                    username  TEXT UNIQUE NOT NULL,
                    senha     TEXT NOT NULL,
                    is_admin  INTEGER NOT NULL DEFAULT 0,
                    criado_em TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            _exec(c, """
                CREATE TABLE IF NOT EXISTS config (
                    chave TEXT PRIMARY KEY,
                    valor TEXT
                )
            """)
        else:
            _exec(c, """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    username  TEXT UNIQUE NOT NULL,
                    senha     TEXT NOT NULL,
                    is_admin  INTEGER NOT NULL DEFAULT 0,
                    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            _exec(c, """
                CREATE TABLE IF NOT EXISTS config (
                    chave TEXT PRIMARY KEY,
                    valor TEXT
                )
            """)
        cur = _exec(c, "SELECT 1 FROM usuarios WHERE username = ?",
                    (ADMIN_USER,))
        if not cur.fetchone():
            _exec(c,
                  "INSERT INTO usuarios (username, senha, is_admin) "
                  "VALUES (?, ?, 1)",
                  (ADMIN_USER, hash_senha(ADMIN_SENHA_INICIAL)))
        _init_leads(c)


def autenticar(username: str, senha: str):
    with get_db() as c:
        cur = _exec(c, "SELECT * FROM usuarios WHERE username = ?",
                    (username,))
        u = cur.fetchone()
    if u and verificar_senha(senha, u["senha"]):
        return {"id": u["id"], "username": u["username"],
                "is_admin": bool(u["is_admin"])}
    return None


def listar_usuarios():
    with get_db() as c:
        cur = _exec(c, "SELECT id, username, is_admin, criado_em "
                       "FROM usuarios ORDER BY id")
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("criado_em") is not None:
            d["criado_em"] = str(d["criado_em"])
        out.append(d)
    return out


def criar_usuario(username: str, senha: str, is_admin: bool = False):
    username = username.strip()
    if not username or not senha:
        return False, "Usuário e senha são obrigatórios."
    try:
        with get_db() as c:
            _exec(c, "INSERT INTO usuarios (username, senha, is_admin) "
                     "VALUES (?, ?, ?)",
                  (username, hash_senha(senha), 1 if is_admin else 0))
        return True, "Usuário criado."
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "duplicate" in msg:
            return False, "Esse nome de usuário já existe."
        return False, f"Erro ao criar usuário: {e}"


def remover_usuario(user_id: int):
    with get_db() as c:
        cur = _exec(c, "SELECT COUNT(*) AS n FROM usuarios "
                       "WHERE is_admin = 1")
        admins = cur.fetchone()["n"]
        cur = _exec(c, "SELECT is_admin FROM usuarios WHERE id = ?",
                    (user_id,))
        alvo = cur.fetchone()
        if not alvo:
            return False, "Usuário não encontrado."
        if alvo["is_admin"] and admins <= 1:
            return False, "Não é possível remover o único administrador."
        _exec(c, "DELETE FROM usuarios WHERE id = ?", (user_id,))
    return True, "Usuário removido."


def alterar_senha(user_id: int, nova_senha: str):
    if not nova_senha:
        return False, "Senha não pode ser vazia."
    with get_db() as c:
        _exec(c, "UPDATE usuarios SET senha = ? WHERE id = ?",
              (hash_senha(nova_senha), user_id))
    return True, "Senha alterada."


def get_config(chave: str, padrao=None):
    with get_db() as c:
        cur = _exec(c, "SELECT valor FROM config WHERE chave = ?",
                    (chave,))
        r = cur.fetchone()
    return r["valor"] if r else padrao


def set_config(chave: str, valor: str):
    with get_db() as c:
        if USE_PG:
            _exec(c, "INSERT INTO config (chave, valor) VALUES (?, ?) "
                     "ON CONFLICT (chave) DO UPDATE SET valor = "
                     "EXCLUDED.valor", (chave, valor))
        else:
            _exec(c, "INSERT INTO config (chave, valor) VALUES (?, ?) "
                     "ON CONFLICT(chave) DO UPDATE SET valor = "
                     "excluded.valor", (chave, valor))


def get_api_key():
    return get_config("api_key", "")


def set_api_key(valor: str):
    set_config("api_key", valor.strip())


# =========================================================
# LEADS — persistência de CNPJs captados
# =========================================================

def _init_leads(c):
    """Cria tabelas de leads e captações (chamada dentro de init_db)."""
    if USE_PG:
        _exec(c, """
            CREATE TABLE IF NOT EXISTS captacoes (
                id          SERIAL PRIMARY KEY,
                usuario_id  INTEGER REFERENCES usuarios(id),
                nome        TEXT NOT NULL DEFAULT 'captacao',
                filtros     TEXT,
                total_leads INTEGER NOT NULL DEFAULT 0,
                criado_em   TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        _exec(c, """
            CREATE TABLE IF NOT EXISTS leads (
                id            SERIAL PRIMARY KEY,
                captacao_id   INTEGER REFERENCES captacoes(id) ON DELETE CASCADE,
                cnpj          TEXT NOT NULL,
                razao_social  TEXT,
                nome_fantasia TEXT,
                situacao      TEXT,
                cnae_principal TEXT,
                cnae_descricao TEXT,
                uf            TEXT,
                municipio     TEXT,
                bairro        TEXT,
                cep           TEXT,
                logradouro    TEXT,
                numero        TEXT,
                complemento   TEXT,
                telefone_1    TEXT,
                telefone_2    TEXT,
                email         TEXT,
                porte         TEXT,
                capital_social TEXT,
                natureza_juridica TEXT,
                data_abertura TEXT,
                data_situacao TEXT,
                mei           TEXT,
                importado_em  TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        _exec(c, "CREATE INDEX IF NOT EXISTS idx_leads_cnpj ON leads(cnpj)")
        _exec(c, "CREATE INDEX IF NOT EXISTS idx_leads_uf ON leads(uf)")
        _exec(c, "CREATE INDEX IF NOT EXISTS idx_leads_municipio ON leads(municipio)")
        _exec(c, "CREATE INDEX IF NOT EXISTS idx_leads_captacao ON leads(captacao_id)")
    else:
        _exec(c, """
            CREATE TABLE IF NOT EXISTS captacoes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id  INTEGER REFERENCES usuarios(id),
                nome        TEXT NOT NULL DEFAULT 'captacao',
                filtros     TEXT,
                total_leads INTEGER NOT NULL DEFAULT 0,
                criado_em   TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        _exec(c, """
            CREATE TABLE IF NOT EXISTS leads (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                captacao_id   INTEGER REFERENCES captacoes(id) ON DELETE CASCADE,
                cnpj          TEXT NOT NULL,
                razao_social  TEXT,
                nome_fantasia TEXT,
                situacao      TEXT,
                cnae_principal TEXT,
                cnae_descricao TEXT,
                uf            TEXT,
                municipio     TEXT,
                bairro        TEXT,
                cep           TEXT,
                logradouro    TEXT,
                numero        TEXT,
                complemento   TEXT,
                telefone_1    TEXT,
                telefone_2    TEXT,
                email         TEXT,
                porte         TEXT,
                capital_social TEXT,
                natureza_juridica TEXT,
                data_abertura TEXT,
                data_situacao TEXT,
                mei           TEXT,
                importado_em  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        _exec(c, "CREATE INDEX IF NOT EXISTS idx_leads_cnpj ON leads(cnpj)")
        _exec(c, "CREATE INDEX IF NOT EXISTS idx_leads_uf ON leads(uf)")
        _exec(c, "CREATE INDEX IF NOT EXISTS idx_leads_municipio ON leads(municipio)")
        _exec(c, "CREATE INDEX IF NOT EXISTS idx_leads_captacao ON leads(captacao_id)")


def criar_captacao(usuario_id: int, nome: str, filtros_json: str):
    """Cria registro de captação e retorna o ID."""
    with get_db() as c:
        cur = _exec(c,
            "INSERT INTO captacoes (usuario_id, nome, filtros) "
            "VALUES (?, ?, ?)",
            (usuario_id, nome, filtros_json))
        if USE_PG:
            row = c.cursor()
            row.execute("SELECT lastval()")
            return row.fetchone()["lastval"]
        else:
            return cur.lastrowid


def importar_leads(captacao_id: int, leads_list: list):
    """Insere lista de dicts de leads no banco. Retorna total inserido."""
    if not leads_list:
        return 0

    campos = [
        "captacao_id", "cnpj", "razao_social", "nome_fantasia", "situacao",
        "cnae_principal", "cnae_descricao", "uf", "municipio", "bairro",
        "cep", "logradouro", "numero", "complemento",
        "telefone_1", "telefone_2", "email", "porte",
        "capital_social", "natureza_juridica", "data_abertura",
        "data_situacao", "mei",
    ]
    placeholders = ", ".join(["?"] * len(campos))
    sql = f"INSERT INTO leads ({', '.join(campos)}) VALUES ({placeholders})"

    count = 0
    with get_db() as c:
        for lead in leads_list:
            vals = [captacao_id]
            for campo in campos[1:]:
                val = lead.get(campo)
                if val is None and campo == "telefone_1":
                    val = lead.get("ddd_telefone_1") or lead.get("telefone")
                if val is None and campo == "telefone_2":
                    val = lead.get("ddd_telefone_2")
                if val is None and campo == "cnae_principal":
                    val = lead.get("cnae_fiscal") or lead.get("cnae")
                if val is None and campo == "cnae_descricao":
                    val = lead.get("cnae_fiscal_descricao") or lead.get("descricao_cnae")
                if val is None and campo == "nome_fantasia":
                    val = lead.get("fantasia")
                if val is None and campo == "capital_social":
                    val = str(lead.get("capital_social", "")) if lead.get("capital_social") else None
                if val is None and campo == "natureza_juridica":
                    val = lead.get("natureza_juridica_descricao")
                vals.append(str(val).strip() if val else None)
            try:
                _exec(c, sql, tuple(vals))
                count += 1
            except Exception:
                pass
        _exec(c, "UPDATE captacoes SET total_leads = ? WHERE id = ?",
              (count, captacao_id))
    return count


def listar_captacoes(usuario_id: int = None):
    with get_db() as c:
        if usuario_id:
            cur = _exec(c,
                "SELECT c.*, u.username FROM captacoes c "
                "LEFT JOIN usuarios u ON u.id = c.usuario_id "
                "WHERE c.usuario_id = ? ORDER BY c.id DESC", (usuario_id,))
        else:
            cur = _exec(c,
                "SELECT c.*, u.username FROM captacoes c "
                "LEFT JOIN usuarios u ON u.id = c.usuario_id "
                "ORDER BY c.id DESC")
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("criado_em"):
            d["criado_em"] = str(d["criado_em"])
        out.append(d)
    return out


def buscar_leads(captacao_id=None, uf=None, municipio=None,
                 cnae=None, termo=None, com_email=False,
                 com_telefone=False, pagina=1, por_pagina=50):
    where = ["1=1"]
    params = []
    if captacao_id:
        where.append("l.captacao_id = ?")
        params.append(captacao_id)
    if uf:
        where.append("LOWER(l.uf) = ?")
        params.append(uf.strip().lower())
    if municipio:
        where.append("LOWER(l.municipio) LIKE ?")
        params.append(f"%{municipio.strip().lower()}%")
    if cnae:
        where.append("l.cnae_principal LIKE ?")
        params.append(f"%{cnae.strip()}%")
    if termo:
        where.append(
            "(LOWER(l.razao_social) LIKE ? OR l.cnpj LIKE ? "
            "OR LOWER(l.email) LIKE ?)")
        t = f"%{termo.strip().lower()}%"
        params.extend([t, t, t])
    if com_email:
        where.append("l.email IS NOT NULL AND l.email != ''")
    if com_telefone:
        where.append("l.telefone_1 IS NOT NULL AND l.telefone_1 != ''")

    where_sql = " AND ".join(where)
    offset = (pagina - 1) * por_pagina

    with get_db() as c:
        cur = _exec(c,
            f"SELECT COUNT(*) AS total FROM leads l WHERE {where_sql}",
            tuple(params))
        total = cur.fetchone()["total"]
        cur = _exec(c,
            f"SELECT l.* FROM leads l WHERE {where_sql} "
            f"ORDER BY l.id DESC LIMIT ? OFFSET ?",
            tuple(params) + (por_pagina, offset))
        rows = cur.fetchall()
    return [dict(r) for r in rows], total


def stats_leads():
    with get_db() as c:
        cur = _exec(c, "SELECT COUNT(*) AS total FROM leads")
        total = cur.fetchone()["total"]
        cur = _exec(c,
            "SELECT COUNT(*) AS n FROM leads "
            "WHERE email IS NOT NULL AND email != ''")
        com_email = cur.fetchone()["n"]
        cur = _exec(c,
            "SELECT COUNT(*) AS n FROM leads "
            "WHERE telefone_1 IS NOT NULL AND telefone_1 != ''")
        com_tel = cur.fetchone()["n"]
        cur = _exec(c,
            "SELECT COUNT(DISTINCT uf) AS n FROM leads WHERE uf IS NOT NULL")
        ufs = cur.fetchone()["n"]
        cur = _exec(c, "SELECT COUNT(*) AS n FROM captacoes")
        captacoes = cur.fetchone()["n"]
    return {
        "total_leads": total, "com_email": com_email,
        "com_telefone": com_tel, "ufs_distintas": ufs,
        "total_captacoes": captacoes,
    }


def excluir_captacao(captacao_id: int):
    with get_db() as c:
        _exec(c, "DELETE FROM leads WHERE captacao_id = ?", (captacao_id,))
        _exec(c, "DELETE FROM captacoes WHERE id = ?", (captacao_id,))
    return True


def exportar_leads_csv(captacao_id=None, uf=None, municipio=None,
                       cnae=None, termo=None, com_email=False,
                       com_telefone=False):
    leads, _ = buscar_leads(
        captacao_id=captacao_id, uf=uf, municipio=municipio,
        cnae=cnae, termo=termo, com_email=com_email,
        com_telefone=com_telefone, pagina=1, por_pagina=999999)
    return leads
