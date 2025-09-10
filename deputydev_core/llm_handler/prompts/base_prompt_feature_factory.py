from enum import Enum
from typing import Generic, Type, TypeVar

from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels
from deputydev_core.llm_handler.prompts.base_prompt import BasePrompt

PromptFeatures = TypeVar("PromptFeatures", bound=Enum)

# Only getting used in CLI


class BasePromptFeatureFactory(Generic[PromptFeatures]):
    @classmethod
    def get_prompt(cls, model_name: LLModels, feature: PromptFeatures) -> Type[BasePrompt]:
        raise NotImplementedError("This method must be implemented in the child class")
