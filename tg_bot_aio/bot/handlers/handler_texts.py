from aiogram import Router, F
from aiogram.types import Message

from ..middleware import ChatIDChecker
from ..bot_setup import bot, dp, logger

text_router = Router()


@text_router.message(F.text)
async def handle_messages(message: Message):
    logger.info('handle msg')
    await message.answer("and hello to you")
    # await message.answer("group id: " + str(message.chat.id))

text_router.message.middleware(ChatIDChecker())

