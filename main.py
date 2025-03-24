from bot.config.settings import Settings
from bot.core.handler import Handler
from telegram.ext import CommandHandler, MessageHandler, filters, ApplicationBuilder

def main():
    application = ApplicationBuilder().token(Settings.TELEGRAM_TOKEN).build()
    handler = Handler()
    analyzer = MessageHandler(filters.TEXT & ~filters.COMMAND, handler.analyze_message)
    spam_command = CommandHandler("spam", handler.spam_command)
    application.add_handler(analyzer)
    application.add_handler(spam_command)
    application.run_polling()

if __name__ == '__main__':
    main()