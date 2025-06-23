import asyncio
from aerich import Command
from config import TORTOISE_ORM

async def run_migrations():
    # инициализация Aerich
    command = Command(tortoise_config=TORTOISE_ORM, app="models", location="./migrations")
    await command.init()
    await command.init_db(safe=True)    # Создает таблицы, если они не существуют
    await command.migrate()             # Генерирует миграции
    await command.upgrade()             # Применяет миграции

if __name__ == "__main__":
    asyncio.run(run_migrations())
