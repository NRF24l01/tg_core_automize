import asyncio
import json
from telethon import TelegramClient, events
from config import HOST, PORT, SESSION_NAME, API_ID, API_HASH
from datetime import datetime
from modules import Logger, AsyncSocketController, serialize_sender, extract_chat_id
from command_processer import process_message
from tortoise import Tortoise, run_async
from migrate import run_migrations
from models import Module, Chat, ChatModule

to_work_tasks = asyncio.Queue()
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

async def process_tasks():
    while True:
        while not to_work_tasks.empty():
            task = await to_work_tasks.get()
            if task["type"] == 1:
                await client.send_message(int(task["payload"]["to"]), task["payload"]["message"])
                logger.info(f"Done task: sending message to {task['payload']['to']}")
        await asyncio.sleep(0.1)

async def process_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    logger = Logger()
    peername = writer.get_extra_info('peername')
    logger.info(f"Start client processing from {peername}")
    controller = AsyncSocketController(reader, writer)
    
    client_info = None

    # --- HANDSHAKE STAGE ---
    try:
        while not client_info:
            try:
                # Set timeout for handshake
                client_info = await asyncio.wait_for(controller.read_json(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.info(f"Client {peername} did not respond during handshake, disconnecting.")
                writer.close()
                await writer.wait_closed()
                return
            except Exception:
                await asyncio.sleep(0.1)
    except Exception as e:
        logger.info(f"Exception during handshake with {peername}: {e}")
        writer.close()
        await writer.wait_closed()
        return

    client_key = client_info["key"]
    
    db_module = await Module.filter(key=client_key).first()
    if not db_module:
        await controller.send_json({"connected": False, "error": "No module with such key"})
        logger.info(f"Module with key {client_key} not found. Client {peername} disconnected.")
        writer.close()
        await writer.wait_closed()
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
            client_disconnected = False

            # --- READ FROM CLIENT WITH TIMEOUT ---
            try:
                if await controller.data_available():
                    try:
                        # Timeout for reading a message from client
                        data = await asyncio.wait_for(controller.read_json(), timeout=5.0)
                        logger.debug("Received:", data)
                        await to_work_tasks.put(data)
                    except asyncio.TimeoutError:
                        logger.info(f"Client {client_name} did not respond in time, disconnecting.")
                        client_disconnected = True
                        break
                    except Exception as e:
                        logger.info(f"Error reading from client {client_name}: {e}")
                        client_disconnected = True
                        break
            except Exception as e:
                logger.info(f"Exception when polling client {client_name}: {e}")
                client_disconnected = True
                break
            
            # --- SEND TASKS TO CLIENT ---
            q = tasks[client_key]
            while not q.empty():
                task = await q.get()
                
                try:
                    await db_module.refresh_from_db()  # ← Получаем свежие данные из БД
                except Exception as e:
                    logger.info(f"Error refreshing db_module for client {client_name}: {e}")
                    continue

                task["system_config"] = db_module.system_config
                skip = False
                if db_module.system_config.get("skip_private", False) is True and task.get("is_private", False):
                    skip = True 
                
                try:
                    chat = await Chat.filter(chat_id=int(task["payload"]["chat_id"])).first()
                except KeyError as e:
                    if task["type"] in client_required_events:
                        logger.debug(f"Sending {task} to {client_name}")
                        task["config"] = {}
                        try:
                            await asyncio.wait_for(controller.send_json(task), timeout=5.0)
                            break
                        except asyncio.TimeoutError:
                            logger.info(f"Client {client_name} did not respond to send, disconnecting.")
                            client_disconnected = True
                            break
                        except Exception as e:
                            logger.info(f"Error sending to client {client_name}: {e}")
                            client_disconnected = True
                            break
                if chat and not skip:
                    chatmodule = await ChatModule.filter(chat=chat, module=db_module).first()
                    if chatmodule:
                        if task["type"] in client_required_events:
                            task["config"] = chatmodule.config_json
                            logger.debug(f"Sending {task} to {client_name}")
                            try:
                                await asyncio.wait_for(controller.send_json(task), timeout=5.0)
                            except asyncio.TimeoutError:
                                logger.info(f"Client {client_name} did not respond to send, disconnecting.")
                                client_disconnected = True
                                break
                            except Exception as e:
                                logger.info(f"Error sending to client {client_name}: {e}")
                                client_disconnected = True
                                break
                elif skip:
                    task["config"] = {}
                    if task["type"] in client_required_events:
                        logger.debug(f"Sending {task} to {client_name}")
                        try:
                            await asyncio.wait_for(controller.send_json(task), timeout=5.0)
                        except asyncio.TimeoutError:
                            logger.info(f"Client {client_name} did not respond to send, disconnecting.")
                            client_disconnected = True
                            break
                        except Exception as e:
                            logger.info(f"Error sending to client {client_name}: {e}")
                            client_disconnected = True
                            break
            if client_disconnected:
                break

            await asyncio.sleep(0.05)

    except Exception as e:
        raise e
        logger.info(f"Client {client_name} disconnected: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        async with clients_lock:
            clients.discard(client_key)
            tasks.pop(client_key, None)
        logger.info(f"Client {client_name} connection closed and cleaned up.")

async def start_server():
    server = await asyncio.start_server(process_client, HOST, PORT)
    logger.info(f"Socket server running on {HOST}:{PORT}")
    async with server:
        await server.serve_forever()
        
        
@client.on(events.NewMessage())
async def handler(event: events.NewMessage.Event):
    await process_message(event=event, client=client)
    
    sender = extract_chat_id(event)
    message = event.raw_text
    timestamp = event.message.date.strftime('%Y-%m-%d %H:%M:%S')
    
    sender_obj = await event.get_sender()

    # Рассылаем задачу всем клиентам
    async with clients_lock:
        for q in tasks.values():
            task = {
                "type": 1,
                "is_private": event.is_private,
                "payload": {
                    "chat_id": sender,
                    "message": message,
                    "timestamp": timestamp,
                    "my_message": event.message.out,
                    "msg_id": event.message.id,
                    "sender": serialize_sender(sender_obj)
                }
            }
            await q.put(task)


@client.on(events.MessageEdited)
async def message_edited(event: events.MessageEdited.Event):
    async with clients_lock:
        for q in tasks.values():
            task = {
                "type": 2,
                "is_private": event.is_private,
                "payload": {
                    "chat_id": extract_chat_id(event),
                    "message": event.message.text,
                    "sender": event.sender_id,
                    "msg_id": event.message.id,
                }
            }
            await q.put(task)


@client.on(events.MessageDeleted)
async def message_deleted(event: events.MessageDeleted.Event):
    async with clients_lock:
        for msg_id in event.deleted_ids:
            for q in tasks.values():
                task = {
                    "type": 3,
                    "payload": {
                        "msg_id": msg_id,
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
        client.run_until_disconnected(),
        process_tasks()
    )

if __name__ == "__main__":
    asyncio.run(main())