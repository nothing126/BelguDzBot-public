from analytics import log_user_and_event
from telegram.ext import ContextTypes

async def log_all_messages(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "message")

async def log_all_callbacks(update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_and_event(update, context, "callback")
