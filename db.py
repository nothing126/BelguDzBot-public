import sqlite3
from config import DB_PATH

def _connect(path: str):
    con = sqlite3.connect(path, check_same_thread=False)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def init_db():
    with _connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            time TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
        """)
        cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_classes_unique
        ON classes(subject_id, weekday, time)
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            due_date TEXT,
            done INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
        """)
        con.commit()

def db_execute(query, params=(), fetch=False):
    with _connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(query, params)
        res = cur.fetchall() if fetch else None
        con.commit()
        return res