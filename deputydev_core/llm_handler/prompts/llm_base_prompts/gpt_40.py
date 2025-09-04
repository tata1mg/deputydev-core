from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels
from deputydev_core.llm_handler.prompts.base_prompt import BasePrompt


class BaseGPT4POINT1Prompt(BasePrompt):
    model_name = LLModels.GPT_4_POINT_1
