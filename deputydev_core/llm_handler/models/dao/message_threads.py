from tortoise import fields, Model

from app.backend_common.utils.tortoise_wrapper.db import ModelUtilMixin, NaiveDatetimeField


class MessageThread(Model, ModelUtilMixin):
    serializable_keys = {
        "id",
        "session_id",
        "actor",
        "query_id",
        "message_type",
        "conversation_chain",
        "message_data",
        "data_hash",
        "usage",
        "llm_model",
        "prompt_type",
        "prompt_category",
        "call_chain_category",
        "metadata",
        "migrated",
        "created_at",
        "updated_at",
        "cost",
    }

    id = fields.IntField(primary_key=True)
    session_id = fields.IntField()
    actor = fields.TextField()
    query_id = fields.IntField(null=True)
    message_type = fields.TextField()
    conversation_chain = fields.JSONField(null=True)
    message_data = fields.JSONField()
    data_hash = fields.TextField()
    usage = fields.JSONField(null=True)
    llm_model = fields.TextField()
    prompt_type = fields.TextField()
    prompt_category = fields.TextField()
    call_chain_category = fields.TextField()
    metadata = fields.JSONField(null=True)
    migrated = fields.BooleanField(default=False)
    cost = fields.FloatField(null=True)
    created_at = NaiveDatetimeField(auto_now_add=True)
    updated_at = NaiveDatetimeField(auto_now_add=True)

    class Meta:
        table = "message_threads"
        indexes = (("session_id",),)
