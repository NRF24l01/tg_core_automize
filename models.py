import uuid
from tortoise import fields
from tortoise.models import Model
from tortoise import fields
from tortoise.signals import pre_save
from tortoise.exceptions import IntegrityError

import random
import string
from typing import Optional, List


def generate_random_key(length=40) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


class Chat(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    chat_id = fields.BigIntField(unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    modules: fields.ReverseRelation["ChatModule"]
    
    class Meta:
        indexes = ["chat_id"]



class Module(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    name = fields.CharField(max_length=20)
    description = fields.TextField(max_length=200, default="")
    system_config = fields.JSONField(default={})
    
    key = fields.CharField(max_length=40, unique=True, null=True)

    required_msgs = fields.JSONField(default=[])  # Store list of ints here
    default_config_json = fields.JSONField(default={})

    def get_required_msgs(self) -> List[int]:
        # Ensure the list contains only ints
        return [int(x) for x in self.required_msgs]

    def set_required_msgs(self, new_list: List[int]) -> None:
        # Validate input and set
        if not all(isinstance(x, int) for x in new_list):
            raise ValueError("All items must be integers")
        self.required_msgs = new_list
    
    chats: fields.ReverseRelation["ChatModule"]

@pre_save(Module)
async def generate_key_if_missing(sender, instance: Module, using_db, update_fields: Optional[list[str]]):
    if not instance.key:
        for _ in range(5):  # Пять попыток на случай коллизий
            candidate = generate_random_key()
            if not await Module.filter(key=candidate).exists():
                instance.key = candidate
                break
        else:
            raise IntegrityError("Не удалось сгенерировать уникальный ключ после 5 попыток.")


class ChatModule(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    chat = fields.ForeignKeyField("models.Chat", related_name="modules", on_delete=fields.CASCADE)
    module = fields.ForeignKeyField("models.Module", related_name="chats", on_delete=fields.CASCADE)

    connected_at = fields.DatetimeField(auto_now_add=True)
    config_json = fields.JSONField(default={})

    class Meta:
        unique_together = ("chat", "module")
