from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels
from deputydev_core.llm_handler.providers.google.prompts.base_prompts.base_gemini_prompt_handler import (
    BaseGeminiPromptHandler,
)


class BaseGemini2Point5FlashPromptHandler(BaseGeminiPromptHandler):
    model_name = LLModels.GEMINI_2_POINT_5_FLASH
