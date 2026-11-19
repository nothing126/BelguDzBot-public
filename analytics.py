# analytics.py
import json
import sqlite3
import time
from datetime import datetime, UTC

from telegram import Update
from telegram.ext import ContextTypes

from config import ANALYTICS_DB_PATH
from db import _connect


def init_analytics_db() -> None:
    """Создание таблиц аналитики (idempotent)."""
    with _connect(ANALYTICS_DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            language_code TEXT,
            is_bot INTEGER,
            added_at TEXT,
            last_seen TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            chat_id INTEGER,
            chat_type TEXT,
            message_id INTEGER,
            text TEXT,
            command TEXT,
            callback_data TEXT,
            raw_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        """)
        con.commit()


def analytics_execute(query: str, params=(), retries: int = 3, retry_sleep: float = 0.2) -> None:
    """
    Вставки/апдейты в аналитику с мягкими ретраями при кратких блокировках.
    Не скрывает реальные ошибки (например, readonly).
    """
    attempt = 0
    while True:
        try:
            with _connect(ANALYTICS_DB_PATH) as con:
                cur = con.cursor()
                cur.execute("BEGIN")
                cur.execute(query, params)
                con.commit()
                return
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "database is locked" in msg and attempt < retries:
                attempt += 1
                time.sleep(retry_sleep)
                continue
            # readonly/прочие ошибки пробрасываем
            raise


async def log_user_and_event(update: Update, context: ContextTypes.DEFAULT_TYPE, event_type: str) -> None:
    """
    Логируем пользователя и событие. Ошибки аналитики не валят бота.
    """
    try:
        u = update.effective_user
        c = update.effective_chat
        m = update.effective_message
        now = datetime.now(UTC).isoformat()

        # upsert пользователя
        analytics_execute("""
            INSERT INTO users (user_id, username, first_name, last_name, language_code, is_bot, added_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                language_code=excluded.language_code,
                is_bot=excluded.is_bot,
                last_seen=excluded.last_seen
        """, (
            u.id if u else None,
            getattr(u, "username", None),
            getattr(u, "first_name", None),
            getattr(u, "last_name", None),
            getattr(u, "language_code", None),
            int(getattr(u, "is_bot", False)) if u else 0,
            now, now
        ))

        command = None
        text = None
        message_id = None
        callback_data = None

        if update.callback_query:
            q = update.callback_query
            callback_data = q.data
            message_id = q.message.message_id if q.message else None

        if m and m.text:
            text = m.text
            message_id = m.message_id
            if m.entities:
                for e in m.entities:
                    if e.type == "bot_command":
                        command = m.text[e.offset:e.offset + e.length]
                        break

        analytics_execute("""
            INSERT INTO events (user_id, event_type, chat_id, chat_type, message_id, text, command, callback_data, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            u.id if u else None,
            event_type,
            c.id if c else None,
            getattr(c, "type", None),
            message_id,
            text,
            command,
            callback_data,
            json.dumps(update.to_dict(), ensure_ascii=False),
            now
        ))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Analytics log error: {e}")
