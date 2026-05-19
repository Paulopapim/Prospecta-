"""
Camada de dados — SQLite

Guarda:
  - usuarios: login da equipe (senha com hash)
  - config:   a chave de API da Casa dos Dados (1 valor central)

SQLite é um arquivo único, sem servidor, zero configuração.

ATENÇÃO sobre persistência na hospedagem gratuita:
  No plano grátis do Render o disco é efêmero — se o serviço
  reiniciar, o arquivo .db pode ser recriado vazio. Para garantir
  persistência, defina a variável de ambiente DATABASE_PATH apontando
  para um disco persistente (Render: adicione um "Disk" e use o
  caminho dele, ex: /var/data/captador.db) OU migre para Postgres.
  O código abre o banco e RECRIA o admin padrão se ele sumir, então
  o site nunca fica inacessível.
"""

import os
import sqlite3
import hashlib
import secrets
from contextlib import contextmanager

DB_PATH = os.environ.get("DATABASE_PATH", "captador.db")

# Admin inicial (pode/should ser trocado por variável de ambiente)
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_SENHA_INICIAL = os.environ.get("ADMIN_SENHA", "admin123")


# --------------------------------------------------------------------------- #
# Hash de senha (PBKDF2 — seguro, sem dependência externa)
# --------------------------------------------------------------------------- #
def hash_senha(senha: str, salt: str = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 100_000)
    return f"{salt}${dk.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        salt, _ = armazenado.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(hash_senha(senha, salt), armazenado)


# --------------------------------------------------------------------------- #
# Conexão
# --------------------------------------------------------------------------- #
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Cria as tabelas e garante que sempre exista um admin."""
    with get_db() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT UNIQUE NOT NULL,
                senha     TEXT NOT NULL,
                is_admin  INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS config (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )
        """)
        # Garante o admin
        existe = c.execute(
            "SELECT 1 FROM usuarios WHERE username = ?", (ADMIN_USER,)
        ).fetchone()
        if not existe:
            c.execute(
                "INSERT INTO usuarios (username, senha, is_admin) "
                "VALUES (?, ?, 1)",
                (ADMIN_USER, hash_senha(ADMIN_SENHA_INICIAL)),
            )


# --------------------------------------------------------------------------- #
# Usuários
# --------------------------------------------------------------------------- #
def autenticar(username: str, senha: str):
    with get_db() as c:
        u = c.execute(
            "SELECT * FROM usuarios WHERE username = ?", (username,)
        ).fetchone()
    if u and verificar_senha(senha, u["senha"]):
        return {"id": u["id"], "username": u["username"],
                "is_admin": bool(u["is_admin"])}
    return None


def listar_usuarios():
    with get_db() as c:
        rows = c.execute(
            "SELECT id, username, is_admin, criado_em "
            "FROM usuarios ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def criar_usuario(username: str, senha: str, is_admin: bool = False):
    username = username.strip()
    if not username or not senha:
        return False, "Usuário e senha são obrigatórios."
    try:
        with get_db() as c:
            c.execute(
                "INSERT INTO usuarios (username, senha, is_admin) "
                "VALUES (?, ?, ?)",
                (username, hash_senha(senha), 1 if is_admin else 0),
            )
        return True, "Usuário criado."
    except sqlite3.IntegrityError:
        return False, "Esse nome de usuário já existe."


def remover_usuario(user_id: int):
    with get_db() as c:
        # Não deixa remover o último admin
        admins = c.execute(
            "SELECT COUNT(*) n FROM usuarios WHERE is_admin = 1"
        ).fetchone()["n"]
        alvo = c.execute(
            "SELECT is_admin FROM usuarios WHERE id = ?", (user_id,)
        ).fetchone()
        if not alvo:
            return False, "Usuário não encontrado."
        if alvo["is_admin"] and admins <= 1:
            return False, "Não é possível remover o único administrador."
        c.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
    return True, "Usuário removido."


def alterar_senha(user_id: int, nova_senha: str):
    if not nova_senha:
        return False, "Senha não pode ser vazia."
    with get_db() as c:
        c.execute("UPDATE usuarios SET senha = ? WHERE id = ?",
                  (hash_senha(nova_senha), user_id))
    return True, "Senha alterada."


# --------------------------------------------------------------------------- #
# Configuração (chave de API)
# --------------------------------------------------------------------------- #
def get_config(chave: str, padrao=None):
    with get_db() as c:
        r = c.execute(
            "SELECT valor FROM config WHERE chave = ?", (chave,)
        ).fetchone()
    return r["valor"] if r else padrao


def set_config(chave: str, valor: str):
    with get_db() as c:
        c.execute(
            "INSERT INTO config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
            (chave, valor),
        )


def get_api_key():
    return get_config("api_key", "")


def set_api_key(valor: str):
    set_config("api_key", valor.strip())
