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
import sqlite3
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
