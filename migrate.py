import asyncio
from aerich import Command
from config import TORTOISE_ORM
import os

async def run_migrations():
    command = Command(tortoise_config=TORTOISE_ORM, app="models", location="./migrations")
    await command.init()

    migration_exists = os.path.exists("migrations/models/0_20250623232903_init.py")
    if not migration_exists:
        try:
            await command.init_db(safe=False)
        except FileExistsError:
            print("Миграция уже существует. Пропускаем init_db.")
    else:
        print("Миграции уже инициализированы. Пропускаем init_db.")
        
    await command.migrate()             # Генерирует миграции
    await command.upgrade()             # Применяет миграции
    exit(0)

if __name__ == "__main__":
    asyncio.run(run_migrations())
