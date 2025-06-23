from telethon import TelegramClient
from models import Chat

async def process_message(message: str, chat_id: int, client: TelegramClient, from_my: bool = False):
    print(message, chat_id, from_my)
    if not from_my:
        return
    
    if message.strip().startswith("/init"):
        return await process_init_message(message=message, chat_id=chat_id, client=client)
        

async def process_init_message(message: str, chat_id: int, client: TelegramClient):
    msg = await client.send_message(chat_id, f'Запрос на инициализацию чата({chat_id}) принят.')
    user, created = await Chat.get_or_create(
        chat_id=chat_id
    )
    
    if created:
        await msg.edit(f"Запись для нового чата создана, чат {chat_id} добавлен под id: {user.id}")
    else:
        await msg.edit(f"Такой чат уже({chat_id}) был зарегистрирован с id {user.id}")
    return
    