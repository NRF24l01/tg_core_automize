import asyncio
from telethon import TelegramClient, events
from config import HOST, PORT, SESSION_NAME, API_ID, API_HASH, S3_ENDPOINT, S3_PASSWORD, S3_USERNAME, S3_BUCKET
from datetime import datetime, timezone, timedelta
from modules import Logger, AsyncSocketController, serialize_sender, extract_chat_id
from command_processer import process_message
from tortoise import Tortoise, run_async
from migrate import run_migrations
from models import Module, Chat, ChatModule
from boto3 import client as boto3client
from botocore.exceptions import ClientError
from botocore.client import Config
import os
import tempfile
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo

to_work_tasks = asyncio.Queue()
tasks: dict[str, asyncio.Queue] = {}
clients = set()
clients_lock = asyncio.Lock()

s3 = boto3client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_USERNAME,
    aws_secret_access_key=S3_PASSWORD,
    config=Config(signature_version='s3v4'),
    region_name='us-east-1',
)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
logger = Logger()

async def init():
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'models': ['models']}
    )
    await Tortoise.generate_schemas()

async def cleanup_old_s3_files():
    logger = Logger()
    while True:
        logger.info("Запущена задача очистки S3...")
        try:
            paginator = s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=S3_BUCKET)

            now = datetime.now(timezone.utc)
            for page in pages:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    last_modified = obj['LastModified']
                    age = now - last_modified
                    if age > timedelta(days=7):
                        try:
                            await asyncio.to_thread(s3.delete_object, Bucket=S3_BUCKET, Key=key)
                            logger.info(f"Удалён устаревший файл: {key}")
                        except ClientError as e:
                            logger.error(f"Ошибка при удалении {key}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при сканировании S3: {e}")

        await asyncio.sleep(86400)  # раз в сутки

async def process_tasks():
    while True:
        while not to_work_tasks.empty():
            task = await to_work_tasks.get()
            if task["type"] == 1:
                logger.debug(f"Got new task for processing: {task}")
                to_id = int(task["payload"]["to"])
                message_text = task["payload"]["message"]
                reply_to = task["payload"].get("reply_to")

                message = await client.send_message(
                    to_id,
                    message_text,
                    reply_to=reply_to if reply_to is not None else None
                )
                logger.info(f"Done task: sending message to {task['payload']['to']}")
                if task.get("module_name", "") != "" and task.get("require_answer", False):
                    to_return = {}
                    to_return["direct"] = True
                    to_return["target"] = task["module_name"]
                    to_return["message"] = {
                        "id": message.id
                    }
                    to_return["chat_id"] = message.chat_id
                    to_return["type"] = 0
                    await distribute_task_to_clients(to_return)
                    logger.debug("Returned message info")
            elif task["type"] == 2:
                await client.edit_message(task["payload"]["chat_id"], task["payload"]["message_id"], task["payload"]["text"])
        await asyncio.sleep(0.1)

async def distribute_task_to_clients(task):
    """Distribute a task to all connected clients"""
    async with clients_lock:
        for q in tasks.values():
            await q.put(task)

async def send_json_with_timeout(controller, data, timeout=5.0, client_name="Unknown"):
    """Send JSON data with timeout handling"""
    try:
        return await asyncio.wait_for(controller.send_json(data), timeout=timeout)
    except asyncio.TimeoutError:
        logger.info(f"Client {client_name} did not respond to send, disconnecting.")
        return False
    except Exception as e:
        logger.info(f"Error sending to client {client_name}: {e}")
        return False

async def read_json_with_timeout(controller, timeout=5.0, client_name="Unknown"):
    """Read JSON data with timeout handling"""
    try:
        return await asyncio.wait_for(controller.read_json(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.info(f"Client {client_name} did not respond in time, disconnecting.")
        return None
    except Exception as e:
        logger.info(f"Error reading from client {client_name}: {e}")
        return None

async def should_send_to_client(task, db_module, client_required_events):
    """Determine if a task should be sent to a client based on configuration"""
    if task.get("direct", False):
        return task.get("target", "") == db_module.name
    
    # Check if the task type is in required events
    if task["type"] not in client_required_events:
        return False
    
    # Check for private message skipping
    if db_module.system_config.get("skip_private", False) is True and task.get("is_private", False):
        task["config"] = {}
        return True
    
    # Check chat-specific configurations
    try:
        chat_id = int(task["payload"]["chat_id"])
        chat = await Chat.filter(chat_id=chat_id).first()
        if chat:
            chatmodule = await ChatModule.filter(chat=chat, module=db_module).first()
            if chatmodule:
                task["config"] = chatmodule.config_json
                return True
        else:
            task["config"] = {}
            return True
    except KeyError:
        task["config"] = {}
        return True
    
    return False

async def cleanup_client(client_key, client_name, writer):
    """Clean up resources when a client disconnects"""
    writer.close()
    await writer.wait_closed()
    async with clients_lock:
        clients.discard(client_key)
        tasks.pop(client_key, None)
    logger.info(f"Client {client_name} connection closed and cleaned up.")

async def process_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    logger = Logger()
    peername = writer.get_extra_info('peername')
    logger.info(f"Start client processing from {peername}")
    controller = AsyncSocketController(None, reader, writer)
    
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
                    data = await read_json_with_timeout(controller, timeout=5.0, client_name=client_name)
                    if data is None:
                        client_disconnected = True
                        break
                    
                    logger.debug("Received:", data)
                    data["module_name"] = client_name
                    await to_work_tasks.put(data)
            except Exception as e:
                logger.info(f"Exception when polling client {client_name}: {e}")
                client_disconnected = True
                break
            
            # --- SEND TASKS TO CLIENT ---
            q = tasks[client_key]
            while not q.empty():
                task = await q.get()
                logger.debug(f"{client_name} - Got new task, processing")
                
                try:
                    await db_module.refresh_from_db()
                except Exception as e:
                    logger.info(f"Error refreshing db_module for client {client_name}: {e}")
                    continue
                
                task["system_config"] = db_module.system_config
                
                should_send = await should_send_to_client(task, db_module, client_required_events)
                if should_send:
                    logger.debug(f"Sending {task} to {client_name}")
                    if not await send_json_with_timeout(controller, task, timeout=5.0, client_name=client_name):
                        client_disconnected = True
                        break
            
            if client_disconnected:
                break

            await asyncio.sleep(0.05)

    except Exception as e:
        logger.info(f"Client {client_name} disconnected: {e}")
    finally:
        await cleanup_client(client_key, client_name, writer)

async def start_server():
    server = await asyncio.start_server(process_client, HOST, PORT)
    logger.info(f"Socket server running on {HOST}:{PORT}")
    async with server:
        await server.serve_forever()

async def process_media(reply):
    """Process and upload media to S3 if needed"""
    if not reply or not reply.media or not hasattr(reply.media, 'document'):
        logger.debug("Reply does not contain a document")
        return False, None
    
    doc = reply.media.document
    attrs = doc.attributes
    is_voice = any(isinstance(a, DocumentAttributeAudio) and getattr(a, "voice", False) for a in attrs)
    is_round = any(isinstance(a, DocumentAttributeVideo) and getattr(a, "round_message", False) for a in attrs)
    
    logger.debug(f"is_voice={is_voice}, is_round={is_round}")
    
    if not (is_voice or is_round):
        return False, None
    
    media_type = "voice" if is_voice else "round"
    msg_id = reply.id
    extension = ".ogg" if is_voice else ".mp4"
    s3_key = f"{media_type}_{msg_id}{extension}"
    
    logger.debug(f"Generated S3 key: {s3_key}")
    
    try:
        logger.debug(f"Checking if media exists in S3: {s3_key}")
        s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
        logger.info(f"Media already exists in S3: {s3_key}")
        return True, s3_key
    except s3.exceptions.ClientError as e:
        code = e.response["ResponseMetadata"]["HTTPStatusCode"]
        logger.debug(f"S3 head_object response code: {code}")
        if code == 404:
            logger.debug(f"Media not found in S3, downloading and uploading: {s3_key}")
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                logger.debug(f"Downloading media to temporary file: {tmp.name}")
                await client.download_media(reply.media, file=tmp.name)
                tmp.flush()
                tmp.seek(0)
                
                s3.upload_file(tmp.name, S3_BUCKET, s3_key)
                logger.info(f"Uploaded media to S3: {s3_key}")
            os.unlink(tmp.name)
            logger.debug(f"Temporary file deleted: {tmp.name}")
            return True, s3_key
        else:
            logger.error(f"S3 head_object error: {e}")
            return False, None
    except Exception as e:
        logger.error(f"Failed to process media: {e}")
        return False, None

def create_task(event, task_type, **additional_data):
    """Create a task object from an event"""
    if task_type == 1:  # New message
        sender = extract_chat_id(event)
        message = event.raw_text
        timestamp = event.message.date.strftime('%Y-%m-%d %H:%M:%S')
        sender_obj = additional_data.get('sender_obj')
        
        task = {
            "type": task_type,
            "is_private": event.is_private,
            "payload": {
                "chat_id": sender,
                "message": message,
                "timestamp": timestamp,
                "my_message": event.message.out,
                "msg_id": event.message.id,
                "sender": serialize_sender(sender_obj) if sender_obj else None,
            }
        }
        
        # Add media reference if available
        if additional_data.get('media_uploaded') and additional_data.get('s3_key'):
            task["payload"]["reply_to_media_id"] = additional_data.get('s3_key')
        else:
            task["payload"]["reply_to_media_id"] = False
            
        return task
    
    elif task_type == 2:  # Edited message
        return {
            "type": task_type,
            "is_private": event.is_private,
            "payload": {
                "chat_id": extract_chat_id(event),
                "message": event.message.text,
                "sender": event.sender_id,
                "msg_id": event.message.id,
            }
        }
    
    elif task_type == 3:  # Deleted message
        return {
            "type": task_type,
            "payload": {
                "msg_id": additional_data.get('msg_id'),
            }
        }
    
    return None

@client.on(events.NewMessage())
async def handler(event: events.NewMessage.Event):
    await process_message(event=event, client=client)
    
    sender_obj = await event.get_sender()
    
    # Process media if this is a reply
    media_uploaded = False
    s3_key = None
    
    if event.message.reply_to_msg_id:
        logger.debug(f"Message is a reply, ID: {event.message.reply_to_msg_id}")
        try:
            reply = await event.get_reply_message()
            logger.debug(f"Got reply message: ID={reply.id}, media={bool(reply.media)}")
            media_uploaded, s3_key = await process_media(reply)
        except Exception as e:
            logger.error(f"Failed to process reply media: {e}")
    
    task = create_task(event, 1, sender_obj=sender_obj, media_uploaded=media_uploaded, s3_key=s3_key)
    await distribute_task_to_clients(task)

@client.on(events.MessageEdited)
async def message_edited(event: events.MessageEdited.Event):
    task = create_task(event, 2)
    await distribute_task_to_clients(task)

@client.on(events.MessageDeleted)
async def message_deleted(event: events.MessageDeleted.Event):
    for msg_id in event.deleted_ids:
        task = create_task(None, 3, msg_id=msg_id)
        await distribute_task_to_clients(task)

async def main():
    logger.info("Starting...")

    await run_migrations()
    await init()
    
    await client.start()
    logger.info("Telegram client started.")

    await asyncio.gather(
        start_server(),
        client.run_until_disconnected(),
        process_tasks(),
        cleanup_old_s3_files(),
    )

if __name__ == "__main__":
    asyncio.run(main())