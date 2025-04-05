from functools import wraps
from dataclasses import dataclass
import logging
import enum
from typing import List, Union, Callable
from asyncio import sleep as async_sleep
from telegram import Update, ChatMember, Message, User
from telegram.ext import CallbackContext

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("core_utils")

@enum.unique
class BanReason(enum.Enum):
    emoji = 1
    probability = 2
    similiarity = 3
    timeout = 4

@dataclass
class CaptchaCallbackData:
    name: str
    chat_id: int
    user_id: int
    message_id: int
    correct: int
    selected: int
    reason: int

@dataclass
class CaptchaJobData:
    chat_id: int
    user_id: int
    user_name: str
    message_id: int
    query_message: Message

def check_is_admin(func: callable):
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs) -> Message:
            try:
                chat_id = update.effective_chat.id
                user_id = update.effective_user.id
                chat_member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if chat_member.status not in [ChatMember.OWNER, ChatMember.ADMINISTRATOR]:
                    return await update.message.reply_text(text="У вас нет прав на эту команду")
                return await func(update, context, *args, **kwargs)  
            except Exception as e:
                logger.error(f"Ошибка обработки команды\n{e}")    
    return wrapper

def delete_reply_on_command(delay: int):
    def decorator(func: callable):
        @wraps(func)
        async def wrapper(update: Update, context: CallbackContext, *args, **kwargs) -> Message:
            try:
                chat_id = update.effective_chat.id
                bot_reply = await func(update, context, *args, **kwargs)
                bot_reply_id = bot_reply.id
                if isinstance(bot_reply, Message):
                    context.application.create_task(delete_message_with_delay(context=context, chat_id=chat_id, message_id=bot_reply_id, delay=delay))
                return bot_reply
            except Exception as e:
                logger.error(f"Ошибка обработки команды\n{e}")
        return wrapper
    return decorator

def delete_command(delay: int):
    def decorator(func: callable):
        @wraps(func)
        async def wrapper(update: Update, context: CallbackContext, *args, **kwargs) -> Message:
            try:
                chat_id = update.effective_chat.id
                message_id = update.effective_message.id
                context.application.create_task(
                    delete_message_with_delay(context=context, chat_id=chat_id, message_id=message_id, delay=delay)
                )
                return await func(update, context, *args, **kwargs)
            except Exception as e:
                logger.error(f"Ошибка обработки команды\n{e}")
        return wrapper
    return decorator

async def delete_message_with_delay(context: CallbackContext, chat_id: int, message_id: int, delay: int) -> bool:
    try:
        await async_sleep(delay)
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception as e:
        logger.error(f"Ошибка обработки команды\n{e}")
        return False

async def ban_user_with_delay(context: CallbackContext, chat_id: int, user_id: int, user_name: str, reason: int, delay: int) -> bool:
    try:
        await async_sleep(delay)
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        logger.info(f"Пользователь: {user_id}, {user_name}. Действие: бан. Причина: {BanReason(value=reason).name}")
        return True
    except Exception as e:
        logger.error(f"Ошибка бана пользователя\n{e}")
        return False

def apply_ban(context: CallbackContext, chat_id: int, user_id: int, user_name: str, message_ids: List[int], reason: int, delay: int) -> bool:
    """
    Объединяет логику бана в связку: бан и удаление сообщений
    """
    try:
        context.application.create_task(
            ban_user_with_delay(context=context, chat_id=chat_id, user_id=user_id, user_name=user_name, reason=reason, delay=delay)
        )
        for message_id in message_ids:
            context.application.create_task(
                delete_message_with_delay(context=context, chat_id=chat_id, message_id=message_id, delay=5)
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка обработки бана\n{e}")
        return False