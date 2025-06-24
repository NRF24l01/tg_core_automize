from telethon import TelegramClient, events
from models import Chat

async def process_message(event: events.NewMessage, client: TelegramClient):
    message = event.raw_text
    chat_id = event.sender_id
    from_my = event.message.out
    
    if not from_my:
        return
    
    if message.strip().startswith("/init"):
        return await process_init_message(event=event, client=client)
        

async def process_init_message(event: events.NewMessage, client: TelegramClient):
    chat_id = event.sender_id
    msg = await client.send_message(chat_id, f'Запрос на инициализацию чата({chat_id}) принят.', reply_to=event.message)
    user, created = await Chat.get_or_create(
        chat_id=chat_id
    )
    
    if created:
        await msg.edit(f"Запись для нового чата создана, чат {chat_id} добавлен под id: {user.id}")
    else:
        await msg.edit(f"Такой чат уже({chat_id}) был зарегистрирован с id {user.id}")
    return
    