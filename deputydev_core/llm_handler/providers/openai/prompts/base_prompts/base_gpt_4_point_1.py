from typing import Any, Dict, List, Type

from pydantic import BaseModel

from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels, MessageData
from deputydev_core.llm_handler.prompts.base_prompt import BasePrompt


class BaseGpt4Point1Prompt(BasePrompt):
    model_name = LLModels.GPT_4_POINT_1

    @classmethod
    def get_parsed_response_blocks(cls, response_block: List[MessageData]) -> List[Dict[str, Any]]:
        raise NotImplementedError("This method must be implemented in the child class")

    @classmethod
    def get_text_format(cls) -> Type[BaseModel]:
        raise NotImplementedError("This method must be implemented in the child class")
