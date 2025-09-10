from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels
from deputydev_core.llm_handler.prompts.base_prompt import BasePrompt


class BaseGemini2Point0FlashPrompt(BasePrompt):
    model_name = LLModels.GEMINI_2_POINT_0_FLASH
