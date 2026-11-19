from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from db import db_execute
from analytics import log_user_and_event
from decorators import admin_only
from utils import ADD_SUBJECT_NAME, DELETE_SUBJECT, is_exit

@admin_only
async def add_subject_start(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "callback" if update.callback_query else "command")
    msg = update.effective_message
    await msg.reply_text(
        "📚 Введи название предмета:",
        reply_markup=ReplyKeyboardMarkup([["❌ Выйти"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return ADD_SUBJECT_NAME

@admin_only
async def add_subject_name(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    msg = update.effective_message
    text = (msg.text or "").strip()

    if is_exit(text):
        await msg.reply_text("🚪 Выход из добавления предмета", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if not text:
        await msg.reply_text("⚠️ Название не должно быть пустым. Введи ещё раз или нажми «❌ Выйти».")
        return ADD_SUBJECT_NAME

    try:
        db_execute("INSERT INTO subjects (name) VALUES (?)", (text,))
        await msg.reply_text(f"✅ Предмет «{text}» добавлен", reply_markup=ReplyKeyboardRemove())
    except Exception:
        await msg.reply_text("⚠️ Такой предмет уже существует. Введи другое название или нажми «❌ Выйти».")
        return ADD_SUBJECT_NAME
    return ConversationHandler.END

async def list_subjects(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "command")
    rows = db_execute("SELECT id, name FROM subjects ORDER BY name", fetch=True)
    if not rows:
        await update.effective_message.reply_text("❌ Нет предметов")
        return
    lines = "\n".join(f"{r[0]}. {r[1]}" for r in rows)
    await update.effective_message.reply_text("📚 Предметы:\n" + lines)

@admin_only
async def delete_subject_start(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "callback" if update.callback_query else "command")
    rows = db_execute("SELECT id, name FROM subjects ORDER BY name", fetch=True)
    msg = update.effective_message
    if not rows:
        await msg.reply_text("❌ Нет предметов для удаления")
        return ConversationHandler.END
    keyboard = [[f"{r[0]}: {r[1]}"] for r in rows]
    await msg.reply_text("Выбери предмет для удаления:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
    return DELETE_SUBJECT

async def delete_subject(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    msg = update.effective_message
    try:
        sid = int((msg.text or "").split(":")[0])
    except Exception:
        await msg.reply_text("⚠️ Неверный формат. Выбери предмет кнопкой.")
        return DELETE_SUBJECT
    db_execute("DELETE FROM subjects WHERE id=?", (sid,))
    db_execute("DELETE FROM classes WHERE subject_id=?", (sid,))
    db_execute("DELETE FROM homework WHERE subject_id=?", (sid,))
    await msg.reply_text("✅ Предмет и все связанные данные удалены", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
