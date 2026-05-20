import os
import sqlite3

DB_NAME = "database.db"


def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        api_key TEXT
    )
    """)

    conn.commit()

    # cria admin padrão
    c.execute("SELECT * FROM usuarios WHERE username = ?", ("admin",))
    existe = c.fetchone()

    if not existe:
        c.execute("""
        INSERT INTO usuarios (username, senha, is_admin)
        VALUES (?, ?, ?)
        """, ("admin", "admin123", 1))

    conn.commit()
    conn.close()


def autenticar(username, senha):
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    SELECT * FROM usuarios
    WHERE username = ? AND senha = ?
    """, (username, senha))

    u = c.fetchone()

    conn.close()

    if not u:
        return None

    return dict(u)


def listar_usuarios():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    SELECT id, username, is_admin
    FROM usuarios
    ORDER BY id
    """)

    rows = c.fetchall()

    conn.close()

    return [dict(r) for r in rows]


def criar_usuario(username, senha, is_admin=False):
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute("""
        INSERT INTO usuarios (username, senha, is_admin)
        VALUES (?, ?, ?)
        """, (
            username,
            senha,
            1 if is_admin else 0
        ))

        conn.commit()
        conn.close()

        return True, "Usuário criado."

    except Exception as e:
        return False, str(e)


def remover_usuario(uid):
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute("""
        DELETE FROM usuarios
        WHERE id = ?
        """, (uid,))

        conn.commit()
        conn.close()

        return True, "Usuário removido."

    except Exception as e:
        return False, str(e)


def alterar_senha(uid, senha):
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute("""
        UPDATE usuarios
        SET senha = ?
        WHERE id = ?
        """, (senha, uid))

        conn.commit()
        conn.close()

        return True, "Senha alterada."

    except Exception as e:
        return False, str(e)


def get_api_key():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    SELECT api_key
    FROM config
    ORDER BY id DESC
    LIMIT 1
    """)

    row = c.fetchone()

    conn.close()

    if not row:
        return None

    return row["api_key"]


def set_api_key(api_key):
    conn = get_conn()
    c = conn.cursor()

    c.execute("DELETE FROM config")

    c.execute("""
    INSERT INTO config (api_key)
    VALUES (?)
    """, (api_key,))

    conn.commit()
    conn.close()
