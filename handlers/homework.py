from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from db import db_execute
from analytics import log_user_and_event
from decorators import admin_only
from utils import (
    ADD_HW_SUBJECT, ADD_HW_TEXT, ADD_HW_DUE, DELETE_HW, parse_date
)


from datetime import datetime, UTC

@admin_only
async def add_hw_start(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "callback" if update.callback_query else "command")
    rows = db_execute("SELECT id, name FROM subjects ORDER BY name", fetch=True)
    msg = update.effective_message
    if not rows:
        await msg.reply_text("⚠️ Сначала добавь предмет")
        return ConversationHandler.END
    keyboard = [[f"{r[0]}: {r[1]}"] for r in rows]
    await msg.reply_text("📚 Выбери предмет для ДЗ:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
    return ADD_HW_SUBJECT

@admin_only
async def add_hw_subject(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    msg = update.effective_message
    try:
        sid = int((msg.text or "").split(":")[0])
    except Exception:
        await msg.reply_text("⚠️ Неверный формат. Выбери предмет кнопкой.")
        return ADD_HW_SUBJECT
    exists = db_execute("SELECT 1 FROM subjects WHERE id=?", (sid,), fetch=True)
    if not exists:
        await msg.reply_text("⚠️ Такого предмета нет. Выбери из списка.")
        return ADD_HW_SUBJECT
    context.user_data['subject'] = sid
    await msg.reply_text("📝 Напиши задание:", reply_markup=ReplyKeyboardRemove())
    return ADD_HW_TEXT

@admin_only
async def add_hw_text(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    txt = (update.effective_message.text or "").strip()
    if not txt:
        await update.effective_message.reply_text("⚠️ Текст задания пуст. Введи задание:")
        return ADD_HW_TEXT
    context.user_data['text'] = txt
    await update.effective_message.reply_text("📅 Укажи дату сдачи (ГГГГ-ММ-ДД) или напиши «нет»")
    return ADD_HW_DUE

@admin_only
async def add_hw_due(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    msg = update.effective_message
    due_input = (msg.text or "").strip()
    if due_input.lower() == "нет":
        due = None
    else:
        due = parse_date(due_input)
        if not due:
            await msg.reply_text("⚠️ Неверная дата. Используй формат ГГГГ-ММ-ДД или напиши «нет».")
            return ADD_HW_DUE

    sid = context.user_data.get('subject')
    text = (context.user_data.get('text') or '').strip()
    now = datetime.now(UTC).isoformat()
    if not sid or not text:
        await msg.reply_text("⚠️ Данные потеряны. Начни заново: /add_hw")
        return ConversationHandler.END

    db_execute(
        "INSERT INTO homework (subject_id, text, due_date, created_at) VALUES (?, ?, ?, ?)",
        (sid, text, due, now)
    )
    await msg.reply_text("✅ ДЗ добавлено")
    return ConversationHandler.END

async def list_hw(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update , context, "command")
    rows = db_execute("""
        SELECT homework.id, subjects.name, homework.text, homework.due_date, homework.done
        FROM homework JOIN subjects ON homework.subject_id=subjects.id
        ORDER BY COALESCE(homework.due_date, '9999-12-31'), homework.created_at
    """, fetch=True)
    if not rows:
        await update.effective_message.reply_text("❌ ДЗ нет")
        return
    lines = [f"{r[0]}. {'✅' if r[4] else '❌'} {r[1]} – {r[2]} (сдать: {r[3] or '—'})" for r in rows]
    await update.effective_message.reply_text("📝 Домашка:\n" + "\n".join(lines))

@admin_only
async def delete_hw_start(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "callback" if update.callback_query else "command")
    rows = db_execute("SELECT id, text FROM homework", fetch=True)
    msg = update.effective_message
    if not rows:
        await msg.reply_text("❌ Нет ДЗ для удаления")
        return ConversationHandler.END
    keyboard = [[f"{r[0]}: {r[1][:48]}"] for r in rows]
    await msg.reply_text("Выбери ДЗ для удаления:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
    return DELETE_HW

async def delete_hw(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    msg = update.effective_message
    try:
        hid = int((msg.text or "").split(":")[0])
    except Exception:
        await msg.reply_text("⚠️ Неверный формат. Выбери кнопкой.")
        return DELETE_HW
    db_execute("DELETE FROM homework WHERE id=?", (hid,))
    await msg.reply_text("✅ ДЗ удалено", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
