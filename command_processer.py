from telethon import TelegramClient, events
from models import Chat, Module

async def process_message(event: events.NewMessage, client: TelegramClient):
    message = event.raw_text
    chat_id = event.sender_id
    from_my = event.message.out
    
    if not from_my:
        return
    
    if message.strip().startswith("/init"):
        return await process_init_message(event=event, client=client)
    elif message.strip().startswith("/modreg"):
        return await process_modreg_message(event=event, client=client)
        

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


async def process_modreg_message(event: events.NewMessage, client: TelegramClient):
    chat_id = event.sender_id
    
    parts = event.raw_text.strip().split()
    if len(parts) < 3:
        await client.send_message(chat_id, f"Проверьте формат сообщения, требуется больше 3х частей({len(parts)}<3)", reply_to=event.message)
        return
    
    msg = await client.send_message(chat_id, f"Обрабатываем запрос", reply_to=event.message)
    
    module_name = parts[1]
    description = ' '.join(parts[2:])
    
    db_module = await Module.filter(name=module_name).first()
    
    if db_module is not None:
        await msg.edit(f"Модуль с именем {db_module.name} найден. Описание:\n```{db_module.description}```")
        return
    
    module = await Module.create(name=module_name, description=description)
    
    await msg.edit(f"Модуль был успешно создан\nid: {module.id}\nkey: {module.key}")
    return
    
    