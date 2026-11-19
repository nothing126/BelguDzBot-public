from datetime import datetime
import sqlite3
import pytz
from config import TIMEZONE, ADMIN_IDS, ANALYTICS_DB_PATH

# состояния
(
    ADD_SUBJECT_NAME,
    ADD_CLASS_SUBJECT,
    ADD_CLASS_DAY,
    ADD_CLASS_TIME,
    ADD_HW_SUBJECT,
    ADD_HW_TEXT,
    ADD_HW_DUE,
    DELETE_SUBJECT,
    DELETE_HW,
    DELETE_TODAY_CLASS,
    DELETE_CLASS          # ← новое состояние
) = range(11)


def is_admin(user_id: int) -> bool:
    """
    Гибридная проверка прав администратора:
    1) суперадмины из config.ADMIN_IDS
    2) админы из таблицы admins в analytics.db (ANALYTICS_DB_PATH)

    Ожидаемая схема таблицы admins:
        CREATE TABLE IF NOT EXISTS admins (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER UNIQUE,
          username TEXT,
          added_at TEXT NOT NULL
        );
    """
    try:
        # суперадмины из конфига — всегда True
        if user_id in ADMIN_IDS:
            return True

        # проверка в БД аналитики
        con = sqlite3.connect(ANALYTICS_DB_PATH)
        cur = con.cursor()
        row = cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone()
        con.close()
        return bool(row)
    except Exception:
        # на всякий случай — если с БД что-то не так, не роняем бота
        return user_id in ADMIN_IDS


def is_exit(text: str) -> bool:
    return (text or "").strip().lower() in {"выйти", "exit", "отмена", "cancel", "❌ выйти"}


def weekday_name(i):
    return ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][i % 7]


def parse_time(text):
    try:
        h, m = map(int, (text or "").split(":"))
        if 0 <= h < 24 and 0 <= m < 60:
            return f"{h:02d}:{m:02d}"
    except Exception:
        pass
    return None


def parse_date(text):
    try:
        return datetime.strptime((text or ""), "%Y-%m-%d").date().isoformat()
    except Exception:
        return None


def tz_now():
    return datetime.now(pytz.timezone(TIMEZONE))
