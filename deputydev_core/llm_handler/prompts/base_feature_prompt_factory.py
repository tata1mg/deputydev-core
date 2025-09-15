from typing import Type

from pydantic import BaseModel

from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels
from deputydev_core.llm_handler.prompts.base_prompt import BasePrompt


class BaseFeaturePromptFactory:
    @classmethod
    def get_prompt(cls, model_name: LLModels) -> Type[BasePrompt]:
        raise NotImplementedError("This method must be implemented in the child class")

    @classmethod
    def get_text_format(cls, model_name: LLModels) -> Type[BaseModel]:
        raise NotImplementedError("This method must be implemented in the child class")
