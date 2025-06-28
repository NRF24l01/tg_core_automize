import asyncio
import json
from telethon import TelegramClient, events
from config import HOST, PORT, SESSION_NAME, API_ID, API_HASH
from datetime import datetime
from modules import Logger, AsyncSocketController
from command_processer import process_message
from tortoise import Tortoise, run_async
from migrate import run_migrations
from models import Module, Chat, ChatModule

tasks: dict[str, asyncio.Queue] = {}
clients = set()
clients_lock = asyncio.Lock()

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
logger = Logger()

async def init():
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'models': ['models']}
    )
    await Tortoise.generate_schemas()

async def process_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    logger = Logger()
    peername = writer.get_extra_info('peername')
    logger.info(f"Start client processing from {peername}")
    controller = AsyncSocketController(reader, writer)
    
    client_info = None
    while not client_info:
        try:
            client_info = await controller.read_json()
        except Exception:
            await asyncio.sleep(0.1)

    client_key = client_info["key"]
    
    db_module = await Module.filter(key=client_key).first()
    if not db_module:
        await controller.send_json({"connected": False, "error": "No such module"})
        return
    
    client_name = db_module.name
    client_required_events = db_module.required_msgs
    
    await controller.send_json({"connected": True, "name": client_name})

    async with clients_lock:
        clients.add(client_key)
        if client_key not in tasks:
            tasks[client_key] = asyncio.Queue()

    logger.info(f"Client '{client_name}' requested events with id: {', '.join(map(str, client_required_events))}")

    try:
        while True:
            if await controller.data_available():
                try:
                    data = await controller.read_json()
                    print("Received:", data)
                except Exception as e:
                    logger.info(f"Error reading from client {client_name}: {e}")
            
            q = tasks[client_key]
            while not q.empty():
                task = await q.get()
                chat = await Chat.filter(chat_id=int(task["payload"]["from"])).first()
                if chat:
                    chatmodule = await ChatModule.filter(chat=chat, module=db_module).first()
                    if chatmodule:
                        if task["type"] in client_required_events:
                            task["config"] = chatmodule.config_json
                            await controller.send_json(task)

            await asyncio.sleep(0.05)

    except Exception as e:
        logger.info(f"Client {client_name} disconnected: {e}")
        writer.close()
        await writer.wait_closed()
        async with clients_lock:
            clients.discard(client_name)
            tasks.pop(client_name, None)

async def start_server():
    server = await asyncio.start_server(process_client, HOST, PORT)
    logger.info(f"Socket server running on {HOST}:{PORT}")
    async with server:
        await server.serve_forever()
        
        
@client.on(events.NewMessage())
async def handler(event):
    await process_message(event=event, client=client)
    
    sender = event.chat_id
    message = event.raw_text
    timestamp = event.message.date.strftime('%Y-%m-%d %H:%M:%S')

    # Рассылаем задачу всем клиентам
    async with clients_lock:
        for q in tasks.values():
            task = {
                "type": 1,
                "payload": {
                    "from": sender,
                    "message": message,
                    "timestamp": timestamp
                }
            }
            await q.put(task)

# --- Главный AsyncIO запуск ---
async def main():
    logger.info("Starting...")

    await run_migrations()
    await init()
    
    await client.start()
    logger.info("Telegram client started.")

    await asyncio.gather(
        start_server(),
        client.run_until_disconnected()
    )

if __name__ == "__main__":
    asyncio.run(main())
