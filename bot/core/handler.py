from bot.config.settings import Settings
from bot.core.encoder import TextEncoder
from bot.core.utils import check_is_admin, delete_reply_on_command, delete_command
from bot.data.utils import get_embeddings, write_to_csv
import logging
import emoji
import joblib
from telegram import Update, User
from telegram.ext import CallbackContext

logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("bot_logger")
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler = logging.FileHandler(
    filename=Settings.ROOT_PATH / "data/bot.log",
    mode="a",
    encoding="utf-8"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

class Handler:

    def __init__(self):
        try:
            self.classifier = joblib.load(Settings.CLF_PATH)
        except Exception as e:
            logger.critical(f"Ошибка инициализации классификатора: {e}")
            raise
        try:
            self.encoder = TextEncoder(Settings.MODEL_CLS)
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
            similiarity = self.encoder.compute_similiarity([message], self.embeddings)
            return similiarity > Settings.SIMILIARITY_TRHLD
        except Exception as e:
            logger.error(f"Ошибка измерения косинусной близости: {e}")
            return False
    
    def gauge_probability(self, message: str) -> bool:
        try:
            message_embedding = self.encoder.encode([message])
            probability = self.classifier.predict_proba(message_embedding)[:, 1]
            return probability > Settings.PROBA_TRHLD
        except Exception as e:
            logger.error(f"Ошибка измерения P(y=spam|x): {e}")
            return False 
        
    def log_ban(self, user: User, reason: str):
        logger.info(f"Пользователь: {user.id}, {user.username}. Действие: бан. Причина: {reason}")

    def log_delete(self, user: User, reason: str):
        logger.info(f"Пользователь: {user.id}, {user.username}. Действие: удаление сообщения. Причина: {reason}")

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
            user = update.effective_user
            message_text = update.effective_message.text
            if len(message_text) <= Settings.LEN_TRHLD:
                return
            if user.id in context.chat_data.get("whitelist", set()):
                logger.info(f"Пользователь в белом списке: {user.id}, {user.username}")
                return
            checks = [
                (self.gauge_emoji_frac,  f"Доля эмодзи выше порога"),
                (self.gauge_probability, f"P(y=spam|x) выше порога"),
                (self.gauge_similiarity, f"Косинусная близость выше порога")
            ]
            for check, reason in checks:
                if check(message_text):
                    if context.chat_data.get("bot_mode", Settings.BOT_MODE) == "soft":
                        self.log_delete(user, reason)
                        await self.delete_message(update, context)
                        return
                    else:
                        self.log_ban(user, reason)
                        await self.delete_message(update, context)
                        await self.ban_user(update, context)
                        return        
        except Exception as e:
            logger.error(f"Ошибка анализа сообщения: {e}")

    @delete_command(5)
    @delete_reply_on_command(3)
    async def spam_command(self, update: Update, context: CallbackContext):
        try:
            if update.effective_message.reply_to_message is None:
                return await update.message.reply_text("Ответьте на сообщение, которое вы хотите отметить как спам, используя /spam")
            reply = update.effective_message.reply_to_message
            try:
                write_to_csv(Settings.DATA_PATH, reply.text)
                logger.info(f"Сообщение сохранено:'{reply.text}'")
            except Exception as e:
                logger.error(f"Ошибка сохранения сообщения: {e}")
                await update.message.reply_text("Ошибка сохранения сообщения")
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id, 
                    message_id=reply.message_id
                )
                return
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения: {e}")
        except Exception as e:
            logger.error(f"Ошибка исполнения команды /spam: {e}")

    @delete_command(5)
    @delete_reply_on_command(3)
    @check_is_admin
    async def mode_command(self, update: Update, context: CallbackContext):
        try:
            args = context.args
            if not args:
                current_mode = context.chat_data.get("bot_mode", Settings.BOT_MODE)
                return await update.message.reply_text(f"Текущий режим бота {current_mode}")
            mode = args[0].lower()
            if mode not in ["soft", "hard"]:
                return await update.message.reply_text("Некорректный ввод. Используйте /mode soft или /mode hard")
            context.chat_data["bot_mode"] = mode
            return await update.message.reply_text(f"Режим бота изменен на {mode}")
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

    @delete_command(7)
    @delete_reply_on_command(5)
    @check_is_admin
    async def whitelist_command(self, update: Update, context: CallbackContext):
        try:
            user_to_manage = None
            args = context.args
            if "whitelist" not in context.chat_data:
                context.chat_data["whitelist"] = set()
            if not args or len(args) != 2:
                return await update.message.reply_text(
                    "Используйте: /whitelist add user_id или /whitelist remove user_id"
                )
            if not args[1].isdigit():
                return await update.message.reply_text(
                    "Некорректный id пользователя. Используйте @username_to_id_bot для получения id пользователя"
                )
            try:
                member = await context.bot.get_chat_member(update.effective_chat.id, int(args[1]))
                user_to_manage = member.user.id
            except Exception as e:
                logger.error(f"Пользователь {args[1]} не найден")
                return await update.message.reply_text(f"Пользователь {args[1]} не найден")
            action = args[0].lower()
            if action not in ["add", "remove"]:
                return await update.message.reply_text(
                    "Некорректная команда. Используйте /whitelist add user_id или /whitelist remove user_id"
                )
            if action == "add":
                if user_to_manage in context.chat_data["whitelist"]:
                    return await update.message.reply_text(f"Пользователь {user_to_manage} уже добавлен в whitelist") 
                context.chat_data["whitelist"].add(user_to_manage)
                return await update.message.reply_text(f"Пользователь {user_to_manage} добавлен в whitelist") 
            elif action == "remove":
                try:
                    context.chat_data["whitelist"].remove(user_to_manage)
                    return await update.message.reply_text(f"Пользователь {user_to_manage} удален из whitelist") 
                except KeyError:
                    return await update.message.reply_text(f"Пользователь {user_to_manage} не найден в whitelist")
        except Exception as e:
            logger.error(f"Ошибка исполнения команды /whitelist: {e}")


        