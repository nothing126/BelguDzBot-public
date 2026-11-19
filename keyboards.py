from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import tz_now

def build_weekday_keyboard():
    today = tz_now().weekday()
    labels = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    btns = []
    for i, lab in enumerate(labels):
        mark = " ⭐" if i == today else ""
        btns.append(InlineKeyboardButton(lab + mark, callback_data=f"day_{i}"))
    rows = [btns[0:3], btns[3:6], btns[6:7]]
    rows.append([InlineKeyboardButton("❌ Выйти", callback_data="day_exit")])
    return InlineKeyboardMarkup(rows)