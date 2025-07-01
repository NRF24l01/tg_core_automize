from telethon.tl.types import User, Chat, Channel
from typing import Union, Dict, Any

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
        }

    elif isinstance(sender, Chat):
        return {
            "type": "chat",
            "id": sender.id,
            "title": sender.title,
            "username": getattr(sender, "username", None),
            "participants_count": getattr(sender, "participants_count", None),
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
        }

    else:
        return {
            "type": "unknown",
            "repr": repr(sender),
        }