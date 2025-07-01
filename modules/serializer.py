from telethon.tl.types import User, Chat, Channel, PeerUser, PeerChat, PeerChannel
from typing import Union, Dict, Any, Optional, Union
from telethon.tl.custom.message import Message
from telethon.events import NewMessage


def extract_chat_id(event: Union[NewMessage.Event, Message]) -> Optional[int]:
    """
    Безопасно извлекает chat_id из события или сообщения Telethon.
    
    Возвращает:
        int — chat_id (user_id, chat_id или channel_id в зависимости от типа чата)
        None — если не удалось определить
    """
    peer = getattr(event.message, "peer_id", None)
    if not peer:
        return None

    if isinstance(peer, PeerUser):
        return peer.user_id
    elif isinstance(peer, PeerChat):
        return peer.chat_id
    elif isinstance(peer, PeerChannel):
        return peer.channel_id

    return None

def serialize_sender(sender: Union[User, Chat, Channel]) -> Dict[str, Any]:
    if isinstance(sender, User):
        return {
            "type": "user",
            "id": sender.id,
            "access_hash": getattr(sender, "access_hash", None),
            "first_name": sender.first_name,
            "last_name": sender.last_name,
            "username": sender.username,
            "phone": sender.phone,
            "is_self": sender.is_self,
            "bot": sender.bot,
            "verified": sender.verified,
            "mutual_contact": sender.mutual_contact,
            "name": sender.first_name,
        }

    elif isinstance(sender, Chat):
        return {
            "type": "chat",
            "id": sender.id,
            "title": sender.title,
            "username": getattr(sender, "username", None),
            "participants_count": getattr(sender, "participants_count", None),
            "name": sender.title,
        }

    elif isinstance(sender, Channel):
        return {
            "type": "channel",
            "id": sender.id,
            "access_hash": getattr(sender, "access_hash", None),
            "title": sender.title,
            "username": sender.username,
            "megagroup": sender.megagroup,
            "broadcast": sender.broadcast,
            "verified": sender.verified,
            "name": sender.title,
        }

    else:
        return {
            "type": "unknown",
            "repr": repr(sender),
        }