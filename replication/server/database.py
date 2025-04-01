import sqlite3

class Database:
    def __init__(self, db_name="chat.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                recipient TEXT,
                content TEXT,
                to_deliver INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                auth_token TEXT PRIMARY KEY,
                username TEXT NOT NULL
            );
        """)

    def execute(self, query, params=(), commit=False):
        c = self.conn.cursor()
        c.execute(query, params)
        if commit:
            self.conn.commit()
        if query.strip().upper().startswith("SELECT"):
            return c.fetchall()
        return c.rowcount
