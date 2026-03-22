import subprocess
import sys
import os

from sqlite3 import connect

DB_PATH = os.path.join(os.path.dirname(__file__), "fusionGPT.db")


def _python_executable():
    """Return the path to the Python interpreter.

    In Autodesk Fusion 360, ``sys.executable`` points to the Fusion application
    itself (e.g. ``Fusion360.exe``), not the embedded Python interpreter.
    Passing that path to ``subprocess`` would launch a new Fusion instance and
    trigger the "start a new instance?" dialog.  We locate the real interpreter
    via ``sys.exec_prefix`` instead, which always points to the root of the
    Python installation that is currently running.
    """
    if sys.platform == "win32":
        candidate = os.path.join(sys.exec_prefix, "python.exe")
    else:
        # macOS / Linux – Fusion 360 bundles Python 3; use the versioned name only
        # to avoid accidentally picking up a Python 2 'python' binary.
        candidate = os.path.join(sys.exec_prefix, "bin", "python3")

    if os.path.isfile(candidate):
        return candidate

    # The interpreter could not be found via exec_prefix.  In Fusion 360 this
    # means pip will not be invoked correctly.  Log a clear message so the
    # problem is easy to diagnose, then fall back to sys.executable.
    print(
        f"FusionGPT: WARNING – could not locate the Python interpreter at "
        f"'{candidate}'.  Falling back to sys.executable ('{sys.executable}'), "
        f"which inside Fusion 360 is the Fusion application itself and will "
        f"likely trigger a 'start a new instance' dialog."
    )
    return sys.executable


def install(package):
    subprocess.check_call([_python_executable(), "-m", "pip", "install", package])


def freeze():
    subprocess.check_call([_python_executable(), "-m", "pip", "freeze"])


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
