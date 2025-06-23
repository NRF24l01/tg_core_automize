from tortoise import fields
from tortoise.models import Model

class Chat(Model):
    id = fields.IntField(pk=True)
    chat_id = fields.BigIntField()
    created_at = fields.DatetimeField(auto_now_add=True)
    
    modules: fields.ReverseRelation["ChatModule"]

class Module(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=20)
    description = fields.TextField(max_length=200, default="")
    
    chats: fields.ReverseRelation["ChatModule"]

class ChatModule(Model):
    id = fields.IntField(pk=True)
    chat = fields.ForeignKeyField("models.Chat", related_name="modules", on_delete=fields.CASCADE)
    module = fields.ForeignKeyField("models.Module", related_name="chats", on_delete=fields.CASCADE)
    
    connected_at = fields.DatetimeField(auto_now_add=True)
    config_json = fields.JSONField(default={})
    
    class Meta:
        unique_together = ("chat", "module")
