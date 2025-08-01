import asyncio
from aerich import Command
from config import TORTOISE_ORM
from tortoise import Tortoise
import os
from modules import Logger

async def run_migrations(logger: Logger):
    command = Command(tortoise_config=TORTOISE_ORM, app="models", location="./migrations")
    await command.init()

    migration_exists = os.path.exists("migrations/models/0_20250623232903_init.py")
    if not migration_exists:
        try:
            await command.init_db(safe=False)
        except FileExistsError:
            logger.info("Миграция уже существует. Пропускаем init_db.")
    else:
        logger.info("Миграции уже инициализированы. Пропускаем init_db.")
        
    await command.migrate()
    await command.upgrade()
    await Tortoise.close_connections()

if __name__ == "__main__":
    asyncio.run(run_migrations())
