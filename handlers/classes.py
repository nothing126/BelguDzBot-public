from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from db import db_execute
from analytics import log_user_and_event
from decorators import admin_only
from keyboards import build_weekday_keyboard
from utils import DELETE_CLASS, weekday_name  # импортируем новое состояние
from utils import (
    ADD_CLASS_SUBJECT, ADD_CLASS_DAY, ADD_CLASS_TIME,
    DELETE_TODAY_CLASS, weekday_name, parse_time, tz_now, is_exit
)

async def cancel_message(update):
    msg = update.effective_message
    await msg.reply_text("🚪 Выход", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cancel_callback(update):
    q = update.callback_query
    try: await q.answer()
    except: pass
    await q.message.reply_text("🚪 Выход")
    return ConversationHandler.END

@admin_only
async def delete_class_start(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "callback" if update.callback_query else "command")
    rows = db_execute("""
        SELECT classes.id, subjects.name, classes.weekday, classes.time
        FROM classes
        JOIN subjects ON classes.subject_id = subjects.id
        ORDER BY classes.weekday, classes.time
    """, fetch=True)
    msg = update.effective_message
    if not rows:
        await msg.reply_text("❌ Нет пар для удаления", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    keyboard = [[f"{r[0]}: {weekday_name(r[2])} {r[3]} – {r[1]}"] for r in rows]
    await msg.reply_text("Выбери пару для удаления:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
    return DELETE_CLASS

@admin_only
async def delete_class(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    msg = update.effective_message
    try:
        class_id = int((msg.text or "").split(":")[0])
    except Exception:
        await msg.reply_text("⚠️ Неверный формат. Выбери кнопкой.")
        return DELETE_CLASS
    db_execute("DELETE FROM classes WHERE id=?", (class_id,))
    await msg.reply_text("✅ Пара удалена", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

@admin_only
async def add_class_start(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "callback" if update.callback_query else "command")
    rows = db_execute("SELECT id, name FROM subjects ORDER BY name", fetch=True)
    msg = update.effective_message
    if not rows:
        await msg.reply_text("⚠️ Сначала добавь предмет через /add_subject")
        return ConversationHandler.END
    keyboard = [[f"{r[0]}: {r[1]}"] for r in rows]
    keyboard.append(["❌ Выйти"])
    await msg.reply_text("📚 Выбери предмет:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
    return ADD_CLASS_SUBJECT

@admin_only
async def add_class_subject(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    msg = update.effective_message
    txt = (msg.text or "").strip()
    if is_exit(txt):
        return await cancel_message(update)
    try:
        sid = int(txt.split(":")[0])
    except Exception:
        await msg.reply_text("⚠️ Неверный формат. Выбери предмет кнопкой или нажми «❌ Выйти».")
        return ADD_CLASS_SUBJECT
    exists = db_execute("SELECT 1 FROM subjects WHERE id=?", (sid,), fetch=True)
    if not exists:
        await msg.reply_text("⚠️ Такого предмета нет. Выбери из списка.")
        return ADD_CLASS_SUBJECT
    context.user_data['subject'] = sid
    await msg.reply_text("📅 Выбери день недели:", reply_markup=ReplyKeyboardRemove())
    await msg.reply_text("День:", reply_markup=build_weekday_keyboard())
    return ADD_CLASS_DAY

@admin_only
async def add_class_day_cb(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "callback")
    q = update.callback_query
    data = q.data
    if data == "day_exit":
        return await cancel_callback(update)
    try:
        wd = int(data.split("_")[1])
    except Exception:
        await q.message.reply_text("⚠️ Выбери день недели кнопкой.")
        return ADD_CLASS_DAY
    context.user_data['weekday'] = wd
    await q.message.reply_text(f"Выбран день: {weekday_name(wd)}\n⏰ Введи время пары (HH:MM):")
    return ADD_CLASS_TIME

@admin_only
async def add_class_time(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    msg = update.effective_message
    txt = (msg.text or "").strip()

    if is_exit(txt):
        return await cancel_message(update)

    tm = parse_time(txt)
    if not tm:
        await msg.reply_text("⚠️ Неверное время. Формат HH:MM, например 08:30. Введи ещё раз:")
        return ADD_CLASS_TIME

    sid = context.user_data.get('subject')
    wd  = context.user_data.get('weekday')
    if sid is None or wd is None:
        await msg.reply_text("⚠️ Данные потеряны. Начни заново: /add_class", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    exists = db_execute(
        "SELECT 1 FROM classes WHERE subject_id=? AND weekday=? AND time=?",
        (sid, wd, tm), fetch=True
    )
    if exists:
        await msg.reply_text(f"↺ Такая пара уже есть: {weekday_name(wd)} {tm}", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    db_execute("INSERT INTO classes (subject_id, weekday, time) VALUES (?, ?, ?)", (sid, wd, tm))
    await msg.reply_text(f"✅ Пара добавлена: {weekday_name(wd)} {tm}", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# список/сегодня
async def list_schedule(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "command")
    rows = db_execute("""
        SELECT subjects.name, classes.weekday, classes.time
        FROM classes JOIN subjects ON classes.subject_id=subjects.id
        ORDER BY classes.weekday, classes.time
    """, fetch=True)
    if not rows:
        await update.effective_message.reply_text("📅 Расписание пустое")
        return
    text = "\n".join(f"{weekday_name(r[1])} {r[2]} – {r[0]}" for r in rows)
    await update.effective_message.reply_text("📅 Расписание:\n" + text)

async def today(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "command")
    wd = tz_now().weekday()
    rows = db_execute("""
        SELECT subjects.name, classes.time
        FROM classes JOIN subjects ON classes.subject_id=subjects.id
        WHERE classes.weekday=?
        ORDER BY classes.time
    """, (wd,), fetch=True)
    if not rows:
        await update.effective_message.reply_text("Сегодня пар нет 🎉")
        return
    text = "\n".join(f"{r[1]} – {r[0]}" for r in rows)
    await update.effective_message.reply_text("📅 Сегодня:\n" + text)

# удаление пары за сегодня
@admin_only
async def delete_today_class_start(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "callback" if update.callback_query else "command")
    msg = update.effective_message
    today_wd = tz_now().weekday()
    rows = db_execute("""
        SELECT classes.id, subjects.name, classes.time
        FROM classes 
        JOIN subjects ON classes.subject_id = subjects.id
        WHERE classes.weekday=?
        ORDER BY classes.time
    """, (today_wd,), fetch=True)
    if not rows:
        await msg.reply_text("❌ Сегодня пар нет", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    keyboard = [[f"{r[0]}: {r[2]} – {r[1]}"] for r in rows]
    await msg.reply_text(
        f"Сегодня {weekday_name(today_wd)}. Выбери пару для удаления:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return DELETE_TODAY_CLASS

@admin_only
async def delete_today_class(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")
    msg = update.effective_message
    try:
        class_id = int((msg.text or "").split(":")[0])
    except Exception:
        await msg.reply_text("⚠️ Неверный формат. Выбери кнопкой.")
        return DELETE_TODAY_CLASS
    db_execute("DELETE FROM classes WHERE id=?", (class_id,))
    await msg.reply_text("✅ Пара удалена", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
