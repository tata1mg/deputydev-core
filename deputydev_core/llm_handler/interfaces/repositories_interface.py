from abc import ABC, abstractmethod
from typing import List, Optional
from deputydev_core.llm_handler.models.dto.message_thread_dto import MessageThreadData, MessageThreadDTO, MessageCallChainCategory
from deputydev_core.llm_handler.models.dto.chat_attachments_dto import ChatAttachmentsDTO


class MessageThreadsRepositoryInterface(ABC):
    @abstractmethod
    async def create_message_thread(self, data: MessageThreadData) -> MessageThreadDTO:
        pass

    @abstractmethod
    async def get_message_threads_for_session(
            self,
            session_id: int,
            call_chain_category: MessageCallChainCategory
    ) -> List[MessageThreadDTO]:
        pass

    @abstractmethod
    async def bulk_insert_message_threads(self, data: List[MessageThreadData]) -> List[MessageThreadDTO]:
        pass

    @abstractmethod
    async def get_message_threads_by_ids(self, message_thread_ids: List[int]) -> List[MessageThreadDTO]:
        pass


class ChatAttachmentsRepositoryInterface(ABC):
    @abstractmethod
    async def get_attachment_by_id(self, attachment_id: int) -> Optional[ChatAttachmentsDTO]:
        pass
