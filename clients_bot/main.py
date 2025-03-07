import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clients_bot.bot_setup import bot, dp, logger
from clients_bot.handlers.handler_commands import command_router
from clients_bot.modes.select_files import form_router

current_dir = os.path.dirname(os.path.abspath(__file__))
print(current_dir)
db_path = os.path.join(current_dir, 'database', 'main.db')


async def main():
    dp.include_router(command_router)
    dp.include_router(form_router)
    logger.info("Routers included to dispatcher")
    logger.info("Client bot started...")

    await dp.start_polling(bot, skip_updates=False)


if __name__ == '__main__':
    asyncio.run(main())
