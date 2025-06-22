import asyncio
import json
from telethon import TelegramClient, events
from config import HOST, PORT, SESSION_NAME, API_ID, API_HASH
from datetime import datetime
from modules import Logger

tasks: dict[str, asyncio.Queue] = {}
clients = set()
clients_lock = asyncio.Lock()

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
logger = Logger()

# --- Асинхронный контроллер для работы с сокетом ---
class AsyncSocketController:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer

    async def read_json(self):
        data = await self.reader.readline()
        if not data:
            raise ConnectionError("Disconnected")
        return json.loads(data.decode())

    async def send_json(self, obj):
        msg = (json.dumps(obj) + "\n").encode()
        self.writer.write(msg)
        await self.writer.drain()

# --- Обработка клиента ---
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

    client_name = client_info["name"]
    client_required_events = client_info["required"]
    print(client_info)

    async with clients_lock:
        clients.add(client_name)
        if client_name not in tasks:
            tasks[client_name] = asyncio.Queue()

    logger.info(f"Client '{client_name}' requested events with id: {', '.join(map(str, client_required_events))}")

    try:
        while True:
            if await controller.data_available():
                try:
                    data = await controller.read_json()
                    print("Received:", data)
                except Exception as e:
                    logger.info(f"Error reading from client {client_name}: {e}")
            
            q = tasks[client_name]
            pending = []
            while not q.empty():
                task = await q.get()
                if task["type"] in client_required_events:
                    await controller.send_json(task)
                else:
                    pending.append(task)

            for task in pending:
                await q.put(task)

            await asyncio.sleep(0.05)

    except Exception as e:
        logger.info(f"Client {client_name} disconnected: {e}")
        writer.close()
        await writer.wait_closed()
        async with clients_lock:
            clients.discard(client_name)
            tasks.pop(client_name, None)

# --- Запуск TCP сервера ---
async def start_server():
    server = await asyncio.start_server(process_client, HOST, PORT)
    logger.info(f"Socket server running on {HOST}:{PORT}")
    async with server:
        await server.serve_forever()

# --- Telethon обработчик сообщений ---
@client.on(events.NewMessage())
async def handler(event):
    print("=== NewMessage handler triggered ===")
    sender = event.sender_id
    message = event.raw_text
    timestamp = event.message.date.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] 📩 From {sender}: {message}")

    # Рассылаем задачу всем клиентам
    async with clients_lock:
        print(tasks)
        for q in tasks.values():
            print(q)
            task = {
                "type": "new_message",
                "from": sender,
                "message": message,
                "timestamp": timestamp
            }
            print(f"Putting task into queue: {task}")
            await q.put(task)

# --- Главный AsyncIO запуск ---
async def main():
    logger.info("Starting...")

    await client.start()
    logger.info("Telegram client started.")

    await asyncio.gather(
        start_server(),
        client.run_until_disconnected()
    )

if __name__ == "__main__":
    asyncio.run(main())
