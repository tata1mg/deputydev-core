from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Type

from pydantic import BaseModel

from deputydev_core.llm_handler.dataclasses.main import (
    NonStreamingResponse,
    StreamingResponse,
    UserAndSystemMessages,
)
from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels, MessageData


class BasePrompt(ABC):
    model_name: LLModels
    prompt_type: str
    prompt_category: str
    response_type: Optional[Literal["text", "json_object", "json_schema"]] = "text"

    def __init__(self, params: Dict[str, Any]) -> None:
        self.params = params

    @abstractmethod
    def get_prompt(self) -> UserAndSystemMessages:
        raise NotImplementedError("This method must be implemented in the child class")

    def get_system_prompt(self) -> Optional[str]:
        return None

    @classmethod
    @abstractmethod
    def get_parsed_result(cls, llm_response: NonStreamingResponse) -> List[Any]:
        raise NotImplementedError("This method must be implemented in the child class")

    @classmethod
    async def get_parsed_streaming_events(cls, llm_response: StreamingResponse) -> AsyncIterator[BaseModel]:
        raise NotImplementedError("Streaming not supported for this prompt")

    @classmethod
    @abstractmethod
    async def get_parsed_response_blocks(cls, response_block: List[MessageData]) -> List[BaseModel]:
        raise NotImplementedError("This method must be implemented in the child class")

    @classmethod
    def get_text_format(cls) -> Type[BaseModel]:
        raise NotImplementedError("This method must be implemented in the child class")
