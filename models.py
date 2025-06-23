import uuid
from tortoise import fields
from tortoise.models import Model


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

    chats: fields.ReverseRelation["ChatModule"]


class ChatModule(Model):
    chat = fields.ForeignKeyField("models.Chat", related_name="modules", on_delete=fields.CASCADE)
    module = fields.ForeignKeyField("models.Module", related_name="chats", on_delete=fields.CASCADE)

    connected_at = fields.DatetimeField(auto_now_add=True)
    config_json = fields.JSONField(default={})

    class Meta:
        unique_together = ("chat", "module")
