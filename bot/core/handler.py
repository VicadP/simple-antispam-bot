from bot.config.settings import Settings
from bot.config.settings import HELP_MESSAGE
from bot.core.encoder import TextEncoder
from bot.core.utils import *
from bot.data.utils import get_embeddings
from bot.data.utils import write_to_csv
import logging
import emoji
import joblib
import time
from datetime import datetime
from datetime import timedelta
from numpy import random
from typing import Tuple
from typing import List
from typing import Union
from telegram import Update
from telegram import Chat
from telegram import ChatMember
from telegram import ChatPermissions
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Message
from telegram.ext import CallbackContext

## ======= LOGER ====== ##
logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("bot")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

file_handler = logging.FileHandler(filename=Settings.ROOT_PATH / "data/bot.log", mode="a", encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO) # не засоряем файл debug сообщениями

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.DEBUG)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False

class SpamDetector:

    ## ====== MAIN LOGIC ====== ##
    def __init__(self):
        self._load_component("classifier", joblib.load, Settings.CLF_PATH)
        self._load_component("encoder", TextEncoder, Settings.MODEL_CLS)
        self.pending_users = set() # для пользователей, которые уже получили, но еще не разрешили капчу

    async def analyze_message(self, update: Update, context: CallbackContext) -> bool:
        """
        Считывает все сообщения и проверяет их на спам. Если сообщение определяется как спам, 
        то ограничивает права пользователя и инициализирует капчу.
        """
        try:
            chat_id = update.effective_chat.id
            chat_type = update.effective_chat.type
            user_id = update.effective_user.id
            user_name = update.effective_user.username
            message_text = update.effective_message.text
            chat_member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)

            if chat_type == Chat.PRIVATE:
                await update.message.reply_text(text="Этот бот работает только в групповых чатах")
                logger.debug("Анализ сообщения: отработка проверки на приватный чат")
                return True
            elif chat_member.status in [ChatMember.OWNER, ChatMember.ADMINISTRATOR]:
                logger.debug("Анализ сообщения: отработка проверки на статус пользователя")
                return True
            elif len(message_text) <= Settings.LEN_TRHLD:
                logger.debug("Анализ сообщения: отработка проверки на длинну сообщения")
                return True
            elif user_id in context.chat_data.get("whitelist", set()):
                logger.debug(f"Анализ сообщения: пользователь в белом списке: {user_id}, {user_name}")
                return True
            else:
                checks = [
                    (self._gauge_emoji_frac,  BanReason.emoji.value),
                    (self._gauge_probability, BanReason.probability.value)
                ]
                for check, reason in checks:
                    if check(message=message_text):
                        await self._restrict_user_from_messaging(context=context, chat_id=chat_id, user_id=user_id, lift=False, minutes=1)
                        await self._throw_captcha(update=update, context=context, reason=reason)
                        return True
        except Exception as e:
            logger.error(f"Ошибка хэндлера: анализ сообщения\n{e}")
            return False
        
    async def _throw_captcha(self, update: Update, context: CallbackContext, reason: int) -> bool:
        """
        Выбрасывает капчу пользователю и инициализирует создание timeout job
        """
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            user_name = update.effective_user.username
            message_id = update.effective_message.id

            if not await self._has_captcha(context=context, chat_id=chat_id, user_id=user_id, message_id=message_id):
                question, answers, correct = self._generate_captcha()
                buttons = [
                    InlineKeyboardButton(
                            str(answer),
                            callback_data=f"captcha:{chat_id}:{user_id}:{message_id}:{correct}:{answer}:{reason}" # заменить на dataclass???
                        ) for answer in answers
                    ]
                reply_markup = InlineKeyboardMarkup([buttons])
                query_message = await update.message.reply_text(
                    text=f"Ваше сообщение похоже на спам.\nУ вас есть 30 секунд для прохождения капчи\n\nДля продолжения {question}=",
                    reply_markup=reply_markup,
                    reply_to_message_id=message_id
                )
                self._create_captcha_timeout_job(
                    context=context, 
                    chat_id=chat_id, 
                    user_id=user_id, 
                    user_name=user_name, 
                    message_id=message_id, 
                    query_message=query_message, 
                    wait_time=30
                )
                return True
            else:
                return True
        except Exception as e:
            logger.error(f"Ошибка хэндлера: генерация капчи\n{e}")
            return False
        
    async def handle_captcha(self, update: Update, context: CallbackContext) -> bool:
        """
        Обрабатывает ответ пользователя на капчу. Если ответ правильный, то пользователь добавляется в whitelist и с него снимаются ограничения.
        Если ответ неправильный, то пользователь получает бан.
        """
        try:
            query = update.callback_query
            await query.answer()
            callback_data = self._parse_callback_data(query.data)

            if not callback_data:
                logger.debug("Обработка капчи: неподходящий callback")
                return False
            elif query.from_user.id != callback_data.user_id:
                logger.debug("Обработка капчи: callback от нецелевого пользователя")
                return False
            else:
                self._clear_job_queue(context=context, job_name=f"{callback_data.chat_id}_{callback_data.user_id}_{callback_data.message_id}")
                if callback_data.correct == callback_data.selected:
                    await query.edit_message_text(text="✅ Верификация успешно пройдена. Вы добавлены в whitelist")
                    await self._process_positive_scenario(
                        context=context,
                        chat_id=callback_data.chat_id,
                        user_id=callback_data.user_id,
                        message_id=query.message.id,
                        lift=True,
                        delay=5
                    )
                    return True
                else:
                    await query.edit_message_text(
                        text="❌ Верификация не пройдена. Вы будете удалены из чата.\n\nЕсли произошла ошибка, пишите: @the_vicad"
                    )
                    self._process_negative_scenario(
                        context=context, 
                        chat_id=callback_data.chat_id, 
                        user_id=callback_data.user_id, 
                        user_name="@placeholder",  # нужно ли вобще указывать в логах username?
                        message_ids=[callback_data.message_id, query.message.id], 
                        reason=callback_data.reason, 
                        delay=5
                    )
                    return True
        except Exception as e:
            logger.info(f"Ошибка хэндлера: обработка капчи\n{e}")
            return False

    async def _expire_captcha(self, context: CallbackContext) -> bool:
        """
        Обрабатывает сценарий, когда пользователь не ответил на капчу
        """
        try:
            job_data = context.job.data
        
            await job_data.query_message.edit_text(
                text="⏰ Капча просрочена. Вы будете удалены из чата.\n\nЕсли произошла ошибка, пишите: @the_vicad"
            )
            self._process_negative_scenario(
                context=context, 
                chat_id=job_data.chat_id, 
                user_id=job_data.user_id, 
                user_name=job_data.user_name, 
                message_ids=[job_data.message_id, job_data.query_message.id], 
                reason=4, 
                delay=5
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка хэндлера: исполнение timeout job\n{e}")
            return False
        
    ## ====== HELPER METHODS ====== ##
    def _load_component(self, name: str, loader: object, *args):
        try:
            setattr(self, name, loader(*args))
        except Exception as e:
            logger.critical(f"Ошибка хэлпера: инициализация компонента {name}\n{e}")
            raise

    def _gauge_emoji_frac(self, message: str) -> bool:
        try:
            emoji_count = emoji.emoji_count(message)
            total_count = len(message)
            if total_count == 0:
                logger.debug("Оценка эмодзи: пустое сообщение")
                return False
            emoji_frac = emoji_count / total_count
            return emoji_frac >= Settings.EMOJI_TRHLD
        except Exception as e:
            logger.error(f"Ошибка хэлпера: измерение доли эмодзи\n{e}")
            return False  
        
    def _gauge_probability(self, message: str) -> bool:
        try:
            message_embedding = self.encoder.encode([message])
            probability = self.classifier.predict_proba(message_embedding)[:, 1]
            return probability >= Settings.PROBA_TRHLD
        except Exception as e:
            logger.error(f"Ошибка хэлпера: оценка вероятности спама\n{e}")
            return False         

    async def _restrict_user_from_messaging(
            self, 
            context: CallbackContext, 
            chat_id: int, 
            user_id: int, 
            lift: bool = False, 
            minutes: int = 1
        ) -> bool:
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=self._create_chat_permissions(lift=lift),
                use_independent_chat_permissions=True,
                until_date=int(time.mktime((datetime.now() + timedelta(minutes=minutes)).timetuple())) # локальное время в Unix
            )
            return True
        except Exception as e:
            print(f"Ошибка хэлпера: ограничение прав пользователя\n{e}")
            return False

    def _create_chat_permissions(self, lift: bool = False) -> ChatPermissions:
        return ChatPermissions(
            can_send_messages=lift, 
            can_send_other_messages=lift,
            can_send_polls=lift,
            can_add_web_page_previews=lift,
            can_invite_users=lift,
            can_send_documents=lift,
            can_send_photos=lift,
            can_send_videos=lift,
            can_send_audios=lift,
            can_send_video_notes=lift,
            can_send_voice_notes=lift
        )

    @staticmethod
    def _generate_captcha() -> Tuple[str, List[int], int]:
        try:
            nums = [random.randint(1, 9) for _ in range(2)]
            correct = sum(nums)
            wrongs = [correct + random.randint(1, 5), correct - random.randint(1, 5)]
            answers = [correct] + wrongs
            random.shuffle(answers)
            return f"решите {'+'.join(map(str, nums))}", answers, correct
        except Exception as e:
            logger.error(f"Ошибка хэлпера: генерация капчи\n{e}")
    
    async def _has_captcha(self, context: CallbackContext, chat_id: int, user_id: int, message_id: int) -> bool:
        """
        Обрабатывает сценарий мн-ва сообщений в секунду. Все сообщения после получения капчи и до ее разрешения удаляются.
        """
        try:
            if (chat_id, user_id) in self.pending_users:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                return True
            else:
                self.pending_users.add((chat_id, user_id))
                return False
        except Exception as e:
            logger.info(f"Ошибка хэлпера: проверка наличия капчи\n{e}")
            return False # в сценарии с ошибкой отправляем капчу на последующие сообщения

    def _create_captcha_timeout_job(
            self, 
            context: CallbackContext, 
            chat_id: int, 
            user_id: int, 
            user_name: str, 
            message_id: int, 
            query_message: Message, 
            wait_time: int
        ) -> bool:
        """
        Создает timeout job для капчи. По истечении wait_time (в секундах) капча будет считаться просроченой
        """
        try:
            job_data = CaptchaJobData(chat_id=chat_id, user_id=user_id, user_name=user_name, message_id=message_id, query_message=query_message)

            context.job_queue.run_once(callback=self._expire_captcha, when=wait_time, data=job_data, name=f"{chat_id}_{user_id}_{message_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка хэлпера: создание timeout job\n{e}")
            return False
        
    def _parse_callback_data(self, callback_data: str) -> Union[CaptchaCallbackData, bool]:
        try:
            data_parts = callback_data.split(":")
            if data_parts[0] != "captcha":
                return False
            else:
                return CaptchaCallbackData(
                    name=data_parts[0],
                    chat_id=int(data_parts[1]),
                    user_id=int(data_parts[2]),
                    message_id=int(data_parts[3]),
                    correct=int(data_parts[4]),
                    selected=int(data_parts[5]),
                    reason=int(data_parts[6])
                )
        except Exception as e:
            logger.error(f"Ошибка хэлпера: парсинг callback query\n{e}")
            return False
        
    def _clear_job_queue(self, context: CallbackContext, job_name: str) -> bool:
        try:
            jobs = context.job_queue.get_jobs_by_name(job_name)
            if jobs:
                for job in jobs: 
                    job.schedule_removal()
            return True
        except Exception as e:
            logger.error(f"Ошибка хэлпера: очистка очереди\n{e}")
            return False
           
    def _add_to_whitelist(self, context: CallbackContext, user_id: int) -> bool:
        try:
            whitelist = context.chat_data.setdefault("whitelist", set())
            if user_id in whitelist:
                return True
            else:
                whitelist.add(user_id)
                return True
        except Exception as e:
            logger.error(f"Ошибка хэлпера: добавление в whitelist\n{e}")
            return False

    def _process_negative_scenario(
            self, 
            context: CallbackContext, 
            chat_id: int, 
            user_id: int, 
            user_name: str, 
            message_ids: List[int], 
            reason: int, 
            delay: int
        ) -> bool:
        """
        Обрабатывает сценарий, когда пользователь либо не ответил на капчу, либо ответил неверно
        """
        try:
            context.application.create_task(
                ban_user_with_delay(context=context, chat_id=chat_id, user_id=user_id, user_name=user_name, reason=reason, delay=delay)
            )
            for message_id in message_ids:
                context.application.create_task(
                    delete_message_with_delay(context=context, chat_id=chat_id, message_id=message_id, delay=5)
                )
            self.pending_users.discard((chat_id, user_id))
            return True
        except Exception as e:
            logger.error(f"Ошибка хэлпера: обработка негативного сценария\n{e}")
            return False
        
    async def _process_positive_scenario(
            self,
            context: CallbackContext,
            chat_id: int,
            user_id: int,
            message_id: int,
            lift: bool,
            delay: int
        ) -> bool:
        """
        Обрабатывает сценарий, когда пользователь верно решил капчу
        """
        try:
            self._add_to_whitelist(context=context, user_id=user_id)
            await self._restrict_user_from_messaging(context=context, chat_id=chat_id, user_id=user_id, lift=lift, minutes=0)      
            context.application.create_task(
                delete_message_with_delay(context=context, chat_id=chat_id, message_id=message_id, delay=delay)
            )
            self.pending_users.discard((chat_id, user_id))
            return True
        except Exception as e:
            logger.error(f"Ошибка хэлпера: обработка позитивного сценария\n{e}")
            return False

## ====== COMMANDS ====== ##
@delete_command(60)
@delete_reply_on_command(60)
async def help(update: Update, context: CallbackContext) -> Message:
    try:
        return await update.message.reply_text(text=HELP_MESSAGE, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Ошибка исполнения команды /help\n{e}")
   
@delete_command(5)
@delete_reply_on_command(3)
async def mark(update: Update, context: CallbackContext) -> Message:
    try:
        replied_message = update.effective_message.reply_to_message
        if replied_message is None:
            return await update.message.reply_text(text="Ответьте на сообщение, которое вы хотите отметить как спам, используя /mark")
        else:
            chat_id = update.effective_chat.id
            replied_message_id = replied_message.id
            replied_message_text = replied_message.text
            try:
                write_to_csv(Settings.DATA_PATH, replied_message_text)
                logger.info(f"Команда /mark: сообщение сохранено")
            except Exception as e:
                logger.error(f"Команда /mark: ошибка сохранения сообщения\n{e}")
                return await update.message.reply_text("Сообщение не было сохранено из-за ошибки")
            await context.bot.delete_message(chat_id=chat_id, message_id=replied_message_id)
    except Exception as e:
        logger.error(f"Ошибка исполнения команды /mark\n{e}")

@delete_command(5)
@delete_reply_on_command(3)
@check_is_admin
async def whitelist(update: Update, context: CallbackContext) -> Message:
    try:
        chat_id = update.effective_chat.id
        user_id = None
        args = context.args
        if not args:
            return await update.message.reply_text(text="Используйте: /whitelist remove user_id или /whitelist clear")
        elif "whitelist" not in context.chat_data:
            return await update.message.reply_text(text="Whitelist пуст")
        elif args[0] == "remove":
            if len(args) != 2:
                return await update.message.reply_text(text="Используйте: /whitelist remove user_id")
            elif not args[1].isdigit():
                return await update.message.reply_text(
                    text="Некорректный id пользователя. Используйте @username_to_id_bot для получения id пользователя"
                )
            else:
                try:
                    chat_member = await context.bot.get_chat_member(chat_id=chat_id, user_id=args[1])
                    user_id = chat_member.user.id
                    context.chat_data["whitelist"].remove(user_id)
                    return await update.message.reply_text(text=f"Пользователь {args[1]} удален из whitelist")
                except Exception as e:
                    return await update.message.reply_text(text=f"Пользователь {args[1]} не найден")
        elif args[0] == "clear":
            n = len(context.chat_data["whitelist"])
            context.chat_data["whitelist"].clear()
            return await update.message.reply_text(text=f"Whitelist очищен, удалено {n} элементов")
    except Exception as e:
        logger.error(f"Ошибка исполнения команды /whitelist\n{e}")