import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional, Type

from pydantic import BaseModel

from deputydev_core.llm_handler.dataclasses.main import (
    ConversationTool,
    PromptCacheConfig,
    Reasoning,
    UnparsedLLMCallResponse,
    UserAndSystemMessages,
)
from deputydev_core.llm_handler.dataclasses.unified_conversation_turn import UnifiedConversationTurn
from deputydev_core.llm_handler.interfaces.cancellation_interface import CancellationCheckerInterface
from deputydev_core.llm_handler.models.dto.message_thread_dto import (
    LLModels,
    MessageThreadDTO,
    ToolUseResponseData,
)
from deputydev_core.llm_handler.services.chat_file_upload.dataclasses.chat_file_upload import (
    Attachment,
    ChatAttachmentDataWithObjectBytes,
)
from deputydev_core.utils.app_logger import AppLogger


class BaseLLMProvider(ABC):
    """Abstract LLM interface"""

    def __init__(
        self,
        config: Dict,
        checker: Optional[CancellationCheckerInterface] = None,
    ) -> None:
        self.config = config or {}
        self.checker = checker

    @abstractmethod
    async def build_llm_payload(
        self,
        llm_model: LLModels,
        attachment_data_task_map: Dict[int, asyncio.Task[ChatAttachmentDataWithObjectBytes]],
        prompt: Optional[UserAndSystemMessages] = None,
        attachments: List[Attachment] = [],
        tool_use_response: Optional[ToolUseResponseData] = None,
        previous_responses: List[MessageThreadDTO] = [],
        tools: Optional[List[ConversationTool]] = None,
        tool_choice: Literal["none", "auto", "required"] = "auto",
        feedback: Optional[str] = None,
        cache_config: PromptCacheConfig = PromptCacheConfig(tools=False, system_message=False, conversation=False),
        search_web: bool = False,
        disable_caching: bool = False,
        conversation_turns: List[UnifiedConversationTurn] = [],
    ) -> Dict[str, Any]:
        """
        Formats the conversation as required by the specific LLM.
        Args:
            prompt (Dict[str, str]): A prompt object containing system and user messages.
        Returns:
            Any: Formatted conversation ready to be sent to the LLM.
        """
        raise NotImplementedError("Must implement format_conversation in subclass")

    def _get_model_config(self, model: LLModels) -> Dict[str, Any]:
        llm_models = self.config.get("LLM_MODELS")
        if model.value not in llm_models:
            raise ValueError(f"Model {model.value} not found in configuration")

        return llm_models[model.value]

    async def call_service_client(
        self,
        session_id: int,
        llm_payload: Dict[str, Any],
        model: LLModels,
        stream: bool = False,
        response_type: Optional[Literal["text", "json_object", "json_schema"]] = None,
        parallel_tool_calls: bool = True,
        text_format: Optional[Type[BaseModel]] = None,
        reasoning: Optional[Reasoning] = None,
    ) -> UnparsedLLMCallResponse:
        """
        Calls the LLM service client.
        Args:
            llm_payload (Dict[str, Any]): The formatted conversation to send to the LLM.
            model (LLModels): The LLM model to use.
            stream (bool): If True, stream the response.
            response_type (str): The type of response expected ("text", "json").
        Returns:
            Any: The raw response from the LLM.
        """
        raise NotImplementedError()

    async def get_tokens(
        self,
        content: str,
        model: LLModels,
    ) -> int:
        """
        Gets Token count for each model for chat summary reranking
        Args:
            content (str): Content whose token count is returned
            model(LLModels): The LLM model to use
        Returns:
            int: Token Count of content
        """
        raise NotImplementedError()

    def get_model_token_limit(self, model: LLModels) -> int:
        """Get the input token limit for a specific model."""
        try:
            model_config = self._get_model_config(model)
            return model_config["INPUT_TOKENS_LIMIT"]
        except KeyError:
            AppLogger.log_warn(f"Token limit not found for model {model.value}, using default 100000")
            return 100000  # Conservative default

    async def validate_token_limit_before_call(self, llm_payload: Dict[str, Any], model: LLModels) -> None:
        """
        Validate if the LLM payload is within token limits using the provider's get_tokens method.
        Raises InputTokenLimitExceededException if limit is exceeded.
        """
        try:
            from deputydev_core.exceptions.exceptions import InputTokenLimitExceededError
            from deputydev_core.utils.app_logger import AppLogger

            # Extract content from payload
            payload_content = self._extract_payload_content_for_token_counting(llm_payload)

            # Count tokens using the provider's get_tokens method
            token_count = await self.get_tokens(content=payload_content, model=model)

            # Get model token limit
            token_limit = self.get_model_token_limit(model)

            AppLogger.log_debug(f"Token validation for {model.value}: {token_count}/{token_limit} tokens")

            if token_count > token_limit:
                raise InputTokenLimitExceededError(
                    model_name=model.value,
                    current_tokens=token_count,
                    max_tokens=token_limit,
                    detail=f"LLM payload has {token_count} tokens, exceeding limit of {token_limit} for model {model.value}",
                )

        except InputTokenLimitExceededError:
            # Re-raise token limit exceptions as-is
            raise
        except Exception as e:  # noqa : BLE001
            from deputydev_core.utils.app_logger import AppLogger

            AppLogger.log_error(f"Error validating token limit for model {model.value}: {e}")
            # Don't block the request if token validation fails, just log the error
            pass

    @abstractmethod
    def _extract_payload_content_for_token_counting(self, llm_payload: Dict[str, Any]) -> str:
        """
        Extract the relevant content from LLM payload that will be sent to the LLM for token counting.
        This handles different provider payload structures.
        """
        raise NotImplementedError("Must implement _extract_payload_content_for_token_counting in subclass")
