import asyncio
import uuid
from typing import Any, Dict, List

from deputydev_core.utils.config_manager import ConfigManager

from deputydev_core.llm_handler.models.dto.chat_attachments_dto import ChatAttachmentsData
from deputydev_core.llm_handler.service_clients.aws.services.s3 import AWSS3ServiceClient
from deputydev_core.llm_handler.services.chat_file_upload.dataclasses.chat_file_upload import (
    Attachment,
    ChatAttachmentDataWithObjectBytes,
    PresignedDownloadUrls,
)


class ChatFileUpload:

    s3_client = AWSS3ServiceClient(
        bucket_name=ConfigManager.configs["AWS_S3_BUCKET"]["AWS_BUCKET_NAME"],
        region_name=ConfigManager.configs["AWS_S3_BUCKET"]["AWS_REGION"],
    )

    @classmethod
    def _get_s3_key(cls, file_name: str, folder: str = "image") -> str:
        """
        Generate a unique S3 key for the file
        """
        # Generate a unique S3 key for the file
        s3_object_name = f"{uuid.uuid4()}.{file_name.split('.')[-1]}"
        if folder == "payload":
            s3_path = f"{ConfigManager.configs['CHAT_FILE_UPLOAD']['PAYLOAD_FOLDER_PATH']}"
        else:
            s3_path = f"{ConfigManager.configs['CHAT_IMAGE_UPLOAD']['IMAGE_FOLDER_PATH']}"
        s3_key = f"{s3_path}/{s3_object_name}"
        return s3_key

    @classmethod
    async def get_presigned_urls_for_upload(
        cls, file_name: str, file_type: str, folder: str = "image"
    ) -> PresignedDownloadUrls:
        """
        Generate presigned URLs for uploading and downloading a file, to be given to the client
        """
        # Generate a unique S3 key for the file
        s3_key = cls._get_s3_key(file_name, folder)

        # create presigned URL tasks

        # Generate presigned URLs for uploading and downloading

        upload_and_download_urls = await asyncio.gather(
            cls.s3_client.create_presigned_post_url(
                object_name=file_name,
                content_type=file_type,
                expiry=600,
                s3_key=s3_key,
                min_bytes=0,
                max_bytes=10485760,  # 10 MB limit
            ),
            cls.s3_client.create_presigned_get_url(s3_key=s3_key, expiry=600),
        )
        upload_url = upload_and_download_urls[0]
        download_url = upload_and_download_urls[1]

        # save chat attachment to database
        new_attachment = await ChatAttachmentsRepository.store_new_attachment(
            ChatAttachmentsData(
                s3_key=s3_key,
                file_name=file_name,
                file_type=file_type,
            )
        )

        # Wait for the tasks to complete and assign to return value
        return PresignedDownloadUrls(upload_url=upload_url, download_url=download_url, attachment_id=new_attachment.id)

    @classmethod
    async def get_presigned_url_for_fetch_by_s3_key(cls, s3_key: str) -> str:
        """
        Generate presigned URL for downloading a file, to be given to the client
        """
        # create presigned URL tasks
        download_url = await cls.s3_client.create_presigned_get_url(s3_key=s3_key, expiry=600)
        return download_url

    @classmethod
    async def get_file_data_by_s3_key(cls, s3_key: str) -> bytes:
        """
        Get file data by S3 key
        """
        file_data = await cls.s3_client.get_object(object_name=s3_key)
        return file_data

    @classmethod
    async def delete_file_by_s3_key(cls, s3_key: str) -> None:
        """
        Delete a file from S3 by its key (no DB changes).
        """
        await cls.s3_client.delete_object(object_name=s3_key)

    @classmethod
    async def get_attachment_data_and_metadata(
        cls,
        attachment_id: int,
    ) -> ChatAttachmentDataWithObjectBytes:
        """
        Get attachment data and metadata
        """

        attachment_data = await ChatAttachmentsRepository.get_attachment_by_id(attachment_id=attachment_id)
        if not attachment_data:
            raise ValueError(f"Attachment with id {attachment_id} not found")

        s3_key = attachment_data.s3_key
        object_bytes = await cls.get_file_data_by_s3_key(s3_key=s3_key)

        return ChatAttachmentDataWithObjectBytes(attachment_metadata=attachment_data, object_bytes=object_bytes)

    @classmethod
    def get_attachment_data_task_map(
        cls,
        all_attachments: List[Attachment],
    ) -> Dict[int, asyncio.Task[ChatAttachmentDataWithObjectBytes]]:
        """
        map attachment id to attachment data fetch task
        """
        attachment_data_task_map: Dict[int, Any] = {}
        for attachment in all_attachments:
            if attachment.attachment_id not in attachment_data_task_map:
                attachment_data_task_map[attachment.attachment_id] = asyncio.create_task(
                    cls.get_attachment_data_and_metadata(attachment_id=attachment.attachment_id)
                )

        return attachment_data_task_map
