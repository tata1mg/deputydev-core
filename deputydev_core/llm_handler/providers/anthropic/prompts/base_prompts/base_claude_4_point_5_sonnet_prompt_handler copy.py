from deputydev_core.llm_handler.models.dto.message_thread_dto import LLModels
from deputydev_core.llm_handler.providers.anthropic.prompts.base_prompts.base_claude_prompt_handler import (
    BaseClaudePromptHandler,
)


class BaseClaude4SonnetPromptHandler(BaseClaudePromptHandler):
    model_name = LLModels.CLAUDE_4_SONNET
