from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels
from deputydev_core.llm_handler.providers.openrouter_models.prompts.base_prompts.base_openrouter_model_prompt_handler import (
    BaseOpenrouterModelPromptHandler,
)


class BaseKimiK2Prompt(BaseOpenrouterModelPromptHandler):
    model_name = LLModels.KIMI_K2
