import subprocess
import sys
import os

from sqlite3 import connect

DB_PATH = os.path.join(os.path.dirname(__file__), "fusionGPT.db")


def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


def freeze():
    subprocess.check_call([sys.executable, "-m", "pip", "freeze"])


def get_db_path():
    return DB_PATH


def checkSqlite() -> bool:
    conn = connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='keys'")
    result = cursor.fetchone() is not None
    conn.close()
    return result


def initSqlite():
    conn = connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS keys (
        id    INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
        name  TEXT (255) UNIQUE,
        value TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        id    INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
        name  TEXT (255) UNIQUE,
        value TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS conversations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
        title      TEXT DEFAULT 'New Chat',
        model      TEXT DEFAULT 'gpt-4o',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
        conversation_id INTEGER NOT NULL,
        role            TEXT NOT NULL,
        content         TEXT NOT NULL,
        tool_calls      TEXT,
        tool_call_id    TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    )''')

    conn.commit()
    conn.close()


def migrate_db():
    """Ensure all tables exist (safe to call on existing DB)."""
    conn = connect(DB_PATH)
    cursor = conn.cursor()

    for table_sql in [
        '''CREATE TABLE IF NOT EXISTS settings (
            id    INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            name  TEXT (255) UNIQUE,
            value TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            title      TEXT DEFAULT 'New Chat',
            model      TEXT DEFAULT 'gpt-4o',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            conversation_id INTEGER NOT NULL,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            tool_calls      TEXT,
            tool_call_id    TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )''',
    ]:
        cursor.execute(table_sql)

    conn.commit()
    conn.close()
