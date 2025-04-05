from bot.config.settings import Settings
from bot.core.handler import SpamDetector
from bot.core.handler import help
from bot.core.handler import mark
from bot.core.handler import whitelist
from telegram.ext import CommandHandler
from telegram.ext import CallbackQueryHandler
from telegram.ext import MessageHandler
from telegram.ext import ApplicationBuilder
from telegram.ext import PicklePersistence
from telegram.ext import PersistenceInput
from telegram.ext import filters

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
    spam_detector = SpamDetector()

    application.add_handlers([
        MessageHandler(filters.TEXT & ~filters.COMMAND, spam_detector.analyze_message),
        CallbackQueryHandler(spam_detector.handle_captcha),
        CommandHandler("help", help),
        CommandHandler("mark", mark),
        CommandHandler("whitelist", whitelist)
    ])
    
    application.run_polling()

if __name__ == '__main__':
    main()