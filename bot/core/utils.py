from functools import wraps
import logging
from asyncio import sleep as async_sleep
from telegram import Update, ChatMember, Message
from telegram.ext import CallbackContext

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("wrapper_logger")

def check_is_admin(func: callable):
    @wraps(func)
    async def wrapper(self, update: Update, context: CallbackContext, *args, **kwargs):
            chat = update.effective_chat
            user = update.effective_user
            try:
                member = await chat.get_member(user.id)
            except Exception as e:
                logger.error(f"Ошибка обработки команды: {e}")
            if member.status not in [ChatMember.OWNER, ChatMember.ADMINISTRATOR]:
                return await update.message.reply_text("У вас нет прав на эту команду")
            return await func(self, update, context, *args, **kwargs)      
    return wrapper

def delete_reply_on_command(delay: int = 5):
    def decorator(func: callable):
        @wraps(func)
        async def wrapper(self, update: Update, context: CallbackContext, *args, **kwargs):
            try:
                message = await func(self, update, context, *args, **kwargs)
                if isinstance(message, Message):
                    context.application.create_task(delete_message_with_delay(message, delay))
                return message
            except Exception as e:
                logger.error(f"Ошибка обработки команды: {e}")
        return wrapper
    return decorator

def delete_command(delay: int = 1):
    def decorator(func: callable):
        @wraps(func)
        async def wrapper(self, update: Update, context: CallbackContext, *args, **kwargs):
            try:
                message = update.effective_message
                result = await func(self, update, context, *args, **kwargs)
                context.application.create_task(delete_message_with_delay(message, delay))
                return result
            except Exception as e:
                logger.error(f"Ошибка обработки команды: {e}")
        return wrapper
    return decorator

async def delete_message_with_delay(message: Message, delay: int):
    try:
        await async_sleep(delay)
        await message.delete()
    except Exception as e:
        logger.error(f"Ошибка обработки команды: {e}")