from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from analytics import log_user_and_event
from decorators import admin_only

@admin_only
async def admin_panel(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "command")
    keyboard = [
        [InlineKeyboardButton("➕ Добавить предмет", callback_data="add_subject")],
        [InlineKeyboardButton("❌ Удалить предмет", callback_data="delete_subject")],
        [InlineKeyboardButton("➕ Добавить пару", callback_data="add_class")],
        [InlineKeyboardButton("❌ Удалить пару (сегодня)", callback_data="delete_today_class")],
        [InlineKeyboardButton("❌ Удалить пару", callback_data="delete_class")],
        [InlineKeyboardButton("📝 Добавить ДЗ", callback_data="add_hw")],
        [InlineKeyboardButton("❌ Удалить ДЗ", callback_data="delete_hw")],
    ]
    await update.effective_message.reply_text("⚙️ Админ-панель:", reply_markup=InlineKeyboardMarkup(keyboard))

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    from utils import is_admin
    await log_user_and_event(update, context, "command")
    user_id = update.effective_user.id if update.effective_user else None
    msg = update.effective_message
    if is_admin(user_id):
        txt = (
            "👋 Привет, админ!\n"
            "Тебе доступна админ-панель через /admin\n\n"
            "📚 Предметы:\n"
            "/list_subjects – список предметов\n\n"
            "📅 Расписание:\n"
            "/list_schedule – все пары\n"
            "/today – пары на сегодня\n\n"
            "📝 Домашка:\n"
            "/list_hw – список ДЗ\n"
        )
    else:
        txt = (
            "👋 Привет!\n"
            "Я помогу вести расписание и домашние задания.\n\n"
            "📚 Предметы:\n"
            "/list_subjects – список предметов\n\n"
            "📅 Расписание:\n"
            "/list_schedule – все пары\n"
            "/today – пары на сегодня\n\n"
            "📝 Домашка:\n"
            "/list_hw – список ДЗ\n"
        )
    await msg.reply_text(txt)
