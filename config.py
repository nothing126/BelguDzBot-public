import os

BOT_TOKEN = os.getenv("BOT_TOKEN") or "..."
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # ← корень проекта по файлу

DB_PATH = os.path.join(BASE_DIR, "data.db") # ← АБСОЛЮТНЫЙ путь бд 
ANALYTICS_DB_PATH = os.path.join(BASE_DIR, "analytics.db")  # ← АБСОЛЮТНЫЙ путь аналитики
TIMEZONE = "Europe/Chisinau"
REMINDER_HOUR = 8

ADMIN_IDS = [1200103539, 878022578, 1093664059]# <- tg id админов