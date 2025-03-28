from bot.config.settings import Settings
from bot.core.handler import Handler
from telegram.ext import CommandHandler, MessageHandler, filters, ApplicationBuilder, PicklePersistence, PersistenceInput

def main():
    application = ApplicationBuilder() \
        .token(Settings.TELEGRAM_TOKEN) \
        .persistence(
            persistence=PicklePersistence(
                filepath=Settings.ROOT_PATH / "data/chat_data.pickle",
                store_data=PersistenceInput(bot_data=False, chat_data=True, user_data=False, callback_data=False),
                single_file=True,
                on_flush=False,
                update_interval=60,
            )
        ) \
        .build()
    handler = Handler()
    analyzer = MessageHandler(filters.TEXT & ~filters.COMMAND, handler.analyze_message)
    spam_command = CommandHandler("spam", handler.spam_command)
    mode_command = CommandHandler("mode", handler.mode_command)
    help_command = CommandHandler("help", handler.help_command)
    whitelist_command = CommandHandler("whitelist", handler.whitelist_command)
    application.add_handler(analyzer)
    application.add_handler(spam_command)
    application.add_handler(mode_command)
    application.add_handler(help_command)
    application.add_handler(whitelist_command)
    application.run_polling()

if __name__ == '__main__':
    main()