from bot.config.settings import Settings
from bot.core.encoder import TextEncoder
from bot.core.utils import check_is_admin, delete_reply_on_command, delete_command
from bot.data.utils import get_embeddings, write_to_csv
import logging
import emoji
import joblib
from telegram import Update
from telegram.ext import CallbackContext

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger('httpx').setLevel(logging.WARNING) # убираем шум
logger = logging.getLogger("bot_logger")

class Handler:

    def __init__(self):
        try:
            self.classifier = joblib.load(Settings.CLF_PATH)
        except Exception as e:
            logger.critical(f"Ошибка инициализации классификатора: {e}")
            raise
        try:
            self.encoder_clf = TextEncoder(Settings.MODEL_CLS)
            self.encoder_sts = TextEncoder(Settings.MODEL_STS)
        except Exception as e:
            logger.critical(f"Ошибка инициализации энкодера: {e}")
            raise
        try:
            self.embeddings = get_embeddings()
        except Exception as e:
            logger.critical(f"Ошибка загрузки эмбедингов: {e}")
            raise
        self.whitelist = Settings.WHITELIST

    def gauge_emoji_frac(self, message: str) -> bool:
        try:
            emoji_count = emoji.emoji_count(message)
            total_count = len(message)
            if total_count == 0:
                logger.warning("Пустое сообщение при проверке на эмодзи")
                return False
            emoji_frac = emoji_count / total_count
            return emoji_frac > Settings.EMOJI_TRHLD
        except Exception as e:
            logger.error(f"Ошибка измерения доли эмодзи: {e}")
            return False          

    def gauge_similiarity(self, message: str) -> bool:
        try:
            similiarity = self.encoder_sts.compute_similiarity([message], self.embeddings)
            return similiarity > Settings.SIMILIARITY_TRHLD
        except Exception as e:
            logger.error(f"Ошибка измерения косинусной близости: {e}")
            return False
    
    def gauge_probability(self, message: str) -> bool:
        try:
            message_embedding = self.encoder_clf.encode([message])
            probability = self.classifier.predict_proba(message_embedding)[:, 1]
            return probability > Settings.PROBA_TRHLD
        except Exception as e:
            logger.error(f"Ошибка измерения P(y=spam|x): {e}")
            return False 
        
    def log_ban(self, user_id: int, reason: str):
        logger.info(f"Пользователь: {user_id} забанен. Причина: {reason}")

    def log_delete(self, user_id: int, reason: str):
        logger.info(f"Сообщение пользователя удалено: {user_id}. Причина: {reason}")

    async def delete_message(self, update: Update, context: CallbackContext):
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id, 
                message_id=update.effective_message.id
            )
            return
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")

    async def ban_user(self, update: Update, context: CallbackContext):
        try:
            await context.bot.ban_chat_member(
                chat_id=update.effective_chat.id, 
                user_id=update.effective_user.id
            )
            return
        except Exception as e:
            logger.error(f"Ошибка бана пользователя: {e}")

    async def analyze_message(self, update: Update, context: CallbackContext):
        try:
            user_id = update.effective_user.id
            message_text = update.effective_message.text
            if len(message_text) <= 15:
                return
            if user_id in self.whitelist:
                logger.info(f"Пользователь  в белом списке: {user_id}")
                return
            checks = [
                (self.gauge_emoji_frac,  "Доля эмодзи выше порога"),
                (self.gauge_similiarity,  "Косинусная близость выше порога"),
                (self.gauge_probability, "P(y=spam|x) выше порога"),
            ]
            for check, reason in checks:
                if check(message_text):
                    if Settings.BOT_MODE == "soft":
                        self.log_delete(user_id, reason)
                        await self.delete_message(update, context)
                        return
                    else:
                        self.log_ban(user_id, reason)
                        #await self.ban_user(update, context)
                        return        
        except Exception as e:
            logger.error(f"Ошибка анализа сообщения: {e}")

    @delete_command(5)
    @delete_reply_on_command(3)
    async def spam_command(self, update: Update, context: CallbackContext):
        if update.effective_message.reply_to_message is None:
            return await update.message.reply_text("Ответьте на сообщение, которое вы хотите отметить как спам, используя /spam")
        reply = update.effective_message.reply_to_message
        try:
            write_to_csv(Settings.DATA_PATH, reply.text)
            logger.info(f"Сообщение сохранено:'{reply.text}'")
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения: {e}")
            await update.message.reply_text("Ошибка сохранения сообщения") # критичная функциональность
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id, 
                message_id=reply.message_id
            )
            return
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")    

    @delete_command(5)
    @delete_reply_on_command(3)
    @check_is_admin
    async def mode_command(self, update: Update, context: CallbackContext):
        try:
            if not context.args:
                return await update.message.reply_text(f"Текущий режим бота {Settings.BOT_MODE}")
            mode = context.args[0].lower()
            if mode not in ["soft", "hard"]:
                return await update.message.reply_text("Некорректный ввод. Используйте /mode soft или /mode hard")
            Settings.BOT_MODE = mode
            return await update.message.reply_text(f"Режим бота изменен на {Settings.BOT_MODE}")
        except Exception as e:
            logger.error(f"Ошибка исполнения команды /mode: {e}")

    @delete_command(30)
    @delete_reply_on_command(30)
    async def help_command(self, update: Update, context: CallbackContext):
        help_message = """
Этот бот сканирует все сообщения в группе для определения спама.
Поведение бота зависит от его режима:
    - В режиме `soft` бот удаляет спам сообщения
    - В режиме `hard` бот банит пользователя, отправившего спам сообщение
Режим может быть изменен через команду `/mode` администраторами канала.

У пользователя есть возможность отметить спам сообщение, в случае, если бот его пропустил.
Для этого необходимо ответить на спам сообщение с командой `/spam`, данная команда удаляет пересланное спам сообщение и 
добавляет его в обучающую выборку.
        """
        try:
            return await update.message.reply_text(
                text=help_message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка исполнения команды /help: {e}")