from tortoise import fields, Model

from app.backend_common.utils.tortoise_wrapper.db import ModelUtilMixin, NaiveDatetimeField


class ChatAttachments(Model, ModelUtilMixin):
    serializable_keys = {
        "id",
        "s3_key",
        "file_name",
        "file_type",
        "status",
        "created_at",
        "updated_at",
    }

    id = fields.IntField(primary_key=True)
    s3_key = fields.TextField()
    file_name = fields.TextField()
    file_type = fields.TextField()
    status = fields.TextField(null=True)
    created_at = NaiveDatetimeField(auto_now_add=True)
    updated_at = NaiveDatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_attachments"
