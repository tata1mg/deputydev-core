from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels
from deputydev_core.llm_handler.providers.openrouter_models.prompts.base_prompts.base_openrouter_model_prompt_handler import (
    BaseOpenrouterModelPromptHandler,
)


class BaseGpt4Point1Prompt(BaseOpenrouterModelPromptHandler):
    model_name = LLModels.OPENROUTER_GPT_4_POINT_1
