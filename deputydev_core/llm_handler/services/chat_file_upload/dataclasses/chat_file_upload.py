from typing import Any, Dict, Optional

from pydantic import BaseModel

from deputydev_core.llm_handler.models.dto.chat_attachments_dto import ChatAttachmentsDTO


class PresignedDownloadUrls(BaseModel):
    upload_url: Dict[str, Any]
    download_url: str
    attachment_id: int


class ChatAttachmentDataWithObjectBytes(BaseModel):
    attachment_metadata: ChatAttachmentsDTO
    object_bytes: Optional[bytes] = None


class Attachment(BaseModel):
    attachment_id: int
    attachment_data: Optional[ChatAttachmentDataWithObjectBytes] = None
    get_url: Optional[str] = None
