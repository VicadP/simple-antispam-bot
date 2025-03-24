from bot.config.settings import Settings
from bot.core.encoder import TextEncoder
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
        self.classifier = joblib.load(Settings.CLF_PATH)
        self.encoder_clf = TextEncoder(Settings.MODEL_CLS)
        self.encoder_sts = TextEncoder(Settings.MODEL_STS)
        self.whitelist = Settings.WHITELIST
        self.embeddings = get_embeddings()

    def gauge_emoji_frac(self, message: str) -> bool:
        emoji_count = emoji.emoji_count(message)
        total_count = len(message)
        emoji_frac = emoji_count / total_count
        #logger.info(f"Доля эмодзи : {emoji_frac:.2f}") # вероятно, этот лог лучше перенести на уровень логирования при удалении/бане
        return emoji_frac > Settings.EMOJI_TRHLD

    def gauge_similiarity(self, message: str) -> bool:
        similiarity = self.encoder_sts.compute_similiarity([message], self.embeddings)
        #logger.info(f"Максимальная схожесть: {similiarity:.2f}")
        return similiarity > Settings.SIMILIARITY_TRHLD
    
    def gauge_probability(self, message: str) -> bool:
        message_embedding = self.encoder_clf.encode([message])
        probability = self.classifier.predict_proba(message_embedding)[:, 1]
        #logger.info(f"Вероятность P(y=spam|x) = {probability}")
        return probability > Settings.PROBA_TRHLD
        
    def log_ban(self, user_id: int, message: str, reason: str):
        logger.info(f"Пользователь: {user_id} забанен. Причина: {reason}. Сообщение: '{message}'")

    def log_delete(self, user_id: int, message: str, reason: str):
        logger.info(f"Сообщение: '{message}' удалено. Пользователь: {user_id}. Причина: {reason}")

    async def delete_message(self, context: CallbackContext, chat_id: int, user_id: int, message_id: int):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения пользователя {user_id}: {e}")

    async def ban_user(self, context: CallbackContext, chat_id: int, user_id: int):
        pass # дописать под сценарий бана

    async def analyze_message(self, update: Update, context: CallbackContext):
        chat_id = update.effective_chat.id 
        user_id = update.effective_user.id
        message_id = update.effective_message.id
        message_text = update.effective_message.text

        if len(message_text) <= 15: # короткие сообщения не обрабатываем (не подходят под паттерн спама)
            return
        elif user_id in self.whitelist:
            logger.info(f"Пользователь {user_id} в whitelist-е.")
            return
        elif self.gauge_emoji_frac(message_text):
            self.log_delete(user_id, message_text, "Доля emoji выше порога")
            await self.delete_message(context, chat_id, user_id, message_id)
            return
        elif self.gauge_similiarity(message_text):
            self.log_delete(user_id, message_text, "Cosine similiarity выше порога")
            await self.delete_message(context, chat_id, user_id, message_id)
            return
        elif self.gauge_probability(message_text):
            self.log_delete(user_id, message_text, "P(y=spam|x) выше порога")
            await self.delete_message(context, chat_id, user_id, message_id)
            return

    async def spam_command(self, update: Update, context: CallbackContext):
        if update.effective_message.reply_to_message is None:
            await update.message.reply_text("Ответьте на сообщение, которое вы хотите отметить как спам, используя /spam")
            return
        
        message_id = update.effective_message.message_id
        reply = update.effective_message.reply_to_message

        write_to_csv(Settings.DATA_PATH, reply.text)
        logger.info(f"Сообщение '{reply.text}' добавлено как спам")
    
        try:
            await context.bot.delete_messages(chat_id=reply.chat.id, message_ids=[reply.message_id, message_id])
        except Exception as e:
            logger.error(f"Ошибка обработки команды {e}")