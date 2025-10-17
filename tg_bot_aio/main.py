import asyncio

from bot.bot_setup import bot, dp, logger
from bot.handlers import handler_commands, handler_texts, handler_callback
from bot.modes.indexing import form_router


async def main():
    dp.include_router(handler_commands.command_router)
    dp.include_router(form_router)
    dp.include_router(handler_callback.callback_router)

    logger.info('Routers included to dispatcher')
    logger.info('bot started...')
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
