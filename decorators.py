from telegram.ext import ConversationHandler
from utils import is_admin

def admin_only(handler):
    async def wrapper(update, context):
        user = update.effective_user
        if update.callback_query:
            try:
                await update.callback_query.answer()
            except Exception:
                pass

        if not user or not is_admin(user.id):
            msg = update.effective_message
            if update.callback_query:
                try:
                    await update.callback_query.answer("🚫 Нет доступа", show_alert=True)
                except Exception:
                    pass
            if msg:
                await msg.reply_text("🚫 Эта команда доступна только администраторам")
            return ConversationHandler.END
        return await handler(update, context)
    return wrapper
