import warnings
from telegram.warnings import PTBUserWarning
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters
)
from config import ANALYTICS_DB_PATH
from config import BOT_TOKEN
from db import init_db
from analytics import init_analytics_db
from handlers.admin import admin_panel, start   # ← добавили start сюда
from handlers.subjects import add_subject_start, add_subject_name, list_subjects, delete_subject_start, delete_subject
from handlers.classes import (
    add_class_start, add_class_subject, add_class_day_cb, add_class_time,
    list_schedule, today, delete_today_class_start, delete_today_class,
    delete_class_start, delete_class,   # ← новое
    cancel_callback
)
from handlers.homework import (
    add_hw_start, add_hw_subject, add_hw_text, add_hw_due,
    list_hw, delete_hw_start, delete_hw
)
from handlers.logs import log_all_messages, log_all_callbacks
from utils import ADD_SUBJECT_NAME, ADD_CLASS_SUBJECT, ADD_CLASS_DAY, ADD_CLASS_TIME, \
    ADD_HW_SUBJECT, ADD_HW_TEXT, ADD_HW_DUE, DELETE_SUBJECT, DELETE_HW, DELETE_TODAY_CLASS, DELETE_CLASS

# приглушаем «шумный» warning PTB
warnings.filterwarnings(
    "ignore",
    category=PTBUserWarning,
    message=r"If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message.*",
)

def main():
    init_db()
    init_analytics_db()
    print("Analytics DB path:", ANALYTICS_DB_PATH)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # глобальные логгеры (до остальных)
    app.add_handler(MessageHandler(filters.ALL, log_all_messages), group=-100)
    app.add_handler(CallbackQueryHandler(log_all_callbacks), group=-100)

    # админ-панель и общие команды
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("start", start))            # ← просто start

    app.add_handler(CommandHandler("list_subjects", list_subjects))
    app.add_handler(CommandHandler("list_schedule", list_schedule))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("list_hw", list_hw))

    # разговорные сценарии
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("delete_class", delete_class_start),
            CallbackQueryHandler(delete_class_start, pattern="^delete_class$"),
            CommandHandler("add_subject", add_subject_start),
            CallbackQueryHandler(add_subject_start, pattern="^add_subject$"),
            CommandHandler("delete_subject", delete_subject_start),
            CallbackQueryHandler(delete_subject_start, pattern="^delete_subject$"),

            CommandHandler("add_class", add_class_start),
            CallbackQueryHandler(add_class_start, pattern="^add_class$"),

            CommandHandler("add_hw", add_hw_start),
            CallbackQueryHandler(add_hw_start, pattern="^add_hw$"),
            CommandHandler("delete_hw", delete_hw_start),
            CallbackQueryHandler(delete_hw_start, pattern="^delete_hw$"),

            CommandHandler("delete_today_class", delete_today_class_start),
            CallbackQueryHandler(delete_today_class_start, pattern="^delete_today_class$")
        ],
        states={
            DELETE_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_class)],
            ADD_SUBJECT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_subject_name)],
            DELETE_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_subject)],

            ADD_CLASS_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_class_subject)],
            ADD_CLASS_DAY: [
                CallbackQueryHandler(add_class_day_cb, pattern=r"^day_[0-6]$"),
                CallbackQueryHandler(cancel_callback, pattern=r"^day_exit$"),
            ],
            ADD_CLASS_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_class_time)],

            ADD_HW_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_hw_subject)],
            ADD_HW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_hw_text)],
            ADD_HW_DUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_hw_due)],

            DELETE_HW: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_hw)],
            DELETE_TODAY_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_today_class)]
        },
        fallbacks=[],
        allow_reentry=True,
        per_chat=True,
        per_message=False
    )

    app.add_handler(conv)

    app.run_polling()

if __name__ == "__main__":
    main()
