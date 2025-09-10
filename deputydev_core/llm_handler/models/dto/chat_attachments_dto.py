from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatAttachmentsData(BaseModel):
    file_name: str
    file_type: str
    s3_key: str
    status: Optional[str] = None


class ChatAttachmentsDTO(ChatAttachmentsData):
    id: int
    created_at: datetime
    updated_at: datetime
