import asyncio
import json
import traceback
from enum import Enum
from typing import Any, Dict, Generic, List, Literal, Optional, Sequence, Type, TypeVar, Union, cast, Callable

import xxhash
from deputydev_core.utils.app_logger import AppLogger
from pydantic import BaseModel

# from deputydev_core.llm_handler.caches.code_gen_tasks_cache import CodeGenTasksCache

from deputydev_core.llm_handler.interfaces.caches_interface import SessionCacheInterface
from deputydev_core.llm_handler.interfaces.repositories_interface import MessageThreadsRepositoryInterface, ChatAttachmentsRepositoryInterface
from deputydev_core.llm_handler.interfaces.config_interface import ConfigInterface
from deputydev_core.llm_handler.exceptions.exceptions import InputTokenLimitExceededError, RetryException
from deputydev_core.llm_handler.models.dto.message_thread_dto import (
    ContentBlockCategory,
    ExtendedThinkingContent,
    ExtendedThinkingData,
    FileBlockData,
    FileContent,
    LLModels,
    MessageCallChainCategory,
    MessageThreadActor,
    MessageThreadData,
    MessageThreadDTO,
    MessageType,
    ResponseData,
    TextBlockContent,
    TextBlockData,
    ToolUseRequestContent,
    ToolUseRequestData,
    ToolUseResponseData,
)
# from deputydev_core.llm_handler.repositories.chat_attachments.repository import ChatAttachmentsRepository
# from deputydev_core.llm_handler.repositories.message_threads.repository import (
#     MessageThreadsRepository,
# )
from deputydev_core.llm_handler.exceptions.llm_exceptions import LLMThrottledError
# from deputydev_core.llm_handler.services.chat_file_upload.chat_file_upload import ChatFileUpload
from deputydev_core.llm_handler.services.chat_file_upload.dataclasses.chat_file_upload import (
    Attachment,
    ChatAttachmentDataWithObjectBytes,
)
from deputydev_core.llm_handler.core.base_llm_provider import BaseLLMProvider
from deputydev_core.llm_handler.dataclasses.main import (
    ConversationRole,
    ConversationTool,
    ConversationTurn,
    LLMCallResponseTypes,
    NonStreamingParsedLLMCallResponse,
    NonStreamingResponse,
    ParsedLLMCallResponse,
    PromptCacheConfig,
    StreamingEventType,
    StreamingParsedLLMCallResponse,
    StreamingResponse,
    UnparsedLLMCallResponse,
    UserAndSystemMessages,
)
from deputydev_core.llm_handler.dataclasses.unified_conversation_turn import UnifiedConversationTurn
from deputydev_core.llm_handler.prompts.base_prompt import BasePrompt
from deputydev_core.llm_handler.prompts.base_prompt_feature_factory import (
    BasePromptFeatureFactory,
)
from deputydev_core.llm_handler.providers.anthropic.llm_provider import Anthropic
from deputydev_core.llm_handler.providers.google.llm_provider import Google
from deputydev_core.llm_handler.providers.openai.llm_provider import OpenAI
from deputydev_core.llm_handler.providers.openrouter_models.llm_provider import OpenRouter
from deputydev_core.llm_handler.dataclasses.main import Reasoning
from deputydev_core.llm_handler.interfaces.cancellation_interface import CancellationCheckerInterface

PromptFeatures = TypeVar("PromptFeatures", bound=Enum)



class LLMHandler(Generic[PromptFeatures]):
    # model_to_provider_class_map: Dict[LLModels, Type[BaseLLMProvider]] = {
    #     LLModels.CLAUDE_3_POINT_5_SONNET: Anthropic,
    #     LLModels.CLAUDE_3_POINT_7_SONNET: Anthropic,
    #     LLModels.CLAUDE_4_SONNET: Anthropic,
    #     LLModels.CLAUDE_4_SONNET_THINKING: Anthropic,
    #     LLModels.GPT_4O: OpenAI,
    #     LLModels.GPT_40_MINI: OpenAI,
    #     LLModels.GEMINI_2_POINT_5_PRO: Google,
    #     LLModels.GEMINI_2_POINT_0_FLASH: Google,
    #     LLModels.GEMINI_2_POINT_5_FLASH: Google,
    #     LLModels.GEMINI_2_POINT_5_FLASH_LITE: Google,
    #     LLModels.GPT_4_POINT_1: OpenAI,
    #     LLModels.GPT_4_POINT_1_NANO: OpenAI,
    #     LLModels.GPT_4_POINT_1_MINI: OpenAI,
    #     LLModels.GPT_O3_MINI: OpenAI,
    #     LLModels.KIMI_K2: OpenRouter,
    #     LLModels.QWEN_3_CODER: OpenRouter,
    #     LLModels.OPENROUTER_GPT_5: OpenRouter,
    #     LLModels.OPENROUTER_GPT_5_MINI: OpenRouter,
    #     LLModels.OPENROUTER_GPT_5_NANO: OpenRouter,
    # }

    def __init__(
        self,
        prompt_factory: Type[BasePromptFeatureFactory[PromptFeatures]],
        prompt_features: Type[PromptFeatures],
        message_threads_repo: MessageThreadsRepositoryInterface,
        chat_attachments_repo: ChatAttachmentsRepositoryInterface,
        session_cache: SessionCacheInterface,
        config: ConfigInterface,
        cache_config: PromptCacheConfig = PromptCacheConfig(tools=False, system_message=False, conversation=False),
    ) -> None:
        self.prompt_handler_map = prompt_factory
        self.prompt_features = prompt_features
        self.message_threads_repo = message_threads_repo
        self.chat_attachments_repo = chat_attachments_repo
        self.session_cache = session_cache
        self.config = config
        self.cache_config = cache_config

        # Will hold callables: LLModels -> Callable[[Optional[CancellationCheckerInterface]], BaseLLMProvider]
        self.model_to_provider_class_map: Dict[
            LLModels, Callable[[Optional[CancellationCheckerInterface]], BaseLLMProvider]] = {}
        self._initialize_providers()


    def _initialize_providers(self) -> None:
        """Initialize providers with their specific configurations (factories that accept a checker)."""
        self.model_to_provider_class_map = {
            LLModels.CLAUDE_3_POINT_5_SONNET: lambda checker: Anthropic(
                checker=checker, config=self.config.get_anthropic_config()
            ),
            LLModels.CLAUDE_3_POINT_7_SONNET: lambda checker: Anthropic(
                checker=checker, config=self.config.get_anthropic_config()
            ),
            LLModels.CLAUDE_4_SONNET: lambda checker: Anthropic(
                checker=checker, config=self.config.get_anthropic_config()
            ),
            LLModels.CLAUDE_4_SONNET_THINKING: lambda checker: Anthropic(
                checker=checker, config=self.config.get_anthropic_config()
            ),
            LLModels.GPT_4O: lambda checker: OpenAI(
                checker=checker, config=self.config.get_openai_config()
            ),
            LLModels.GPT_40_MINI: lambda checker: OpenAI(
                checker=checker, config=self.config.get_openai_config()
            ),
            LLModels.GEMINI_2_POINT_5_PRO: lambda checker: Google(
                checker=checker, config=self.config.get_gemini_config()
            ),
            LLModels.GEMINI_2_POINT_0_FLASH: lambda checker: Google(
                checker=checker, config=self.config.get_gemini_config()
            ),
            LLModels.GEMINI_2_POINT_5_FLASH: lambda checker: Google(
                checker=checker, config=self.config.get_gemini_config()
            ),
            LLModels.GEMINI_2_POINT_5_FLASH_LITE: lambda checker: Google(
                checker=checker, config=self.config.get_gemini_config()
            ),
            LLModels.GPT_4_POINT_1: lambda checker: OpenAI(
                checker=checker, config=self.config.get_openai_config()
            ),
            LLModels.GPT_4_POINT_1_NANO: lambda checker: OpenAI(
                checker=checker, config=self.config.get_openai_config()
            ),
            LLModels.GPT_4_POINT_1_MINI: lambda checker: OpenAI(
                checker=checker, config=self.config.get_openai_config()
            ),
            LLModels.GPT_O3_MINI: lambda checker: OpenAI(
                checker=checker, config=self.config.get_openai_config()
            ),
            LLModels.KIMI_K2: lambda checker: OpenRouter(
                checker=checker, config=self.config.get_openrouter_config()
            ),
            LLModels.QWEN_3_CODER: lambda checker: OpenRouter(
                checker=checker, config=self.config.get_openrouter_config()
            ),
            # add more mappings as needed
        }

    def _get_provider(self, llm_model: LLModels, checker: Optional[CancellationCheckerInterface] = None) -> BaseLLMProvider:
        """
        Construct a provider instance for the given llm_model.

        The registry may hold:
          - a factory callable that expects a single `checker` argument (preferred),
          - OR an older-style class/constructor that takes no args.
        This helper tries to call with checker first, then without args.
        """
        factory_or_class = self.model_to_provider_class_map.get(llm_model)
        if factory_or_class is None:
            raise ValueError(f"LLM model {llm_model} not supported")

        # Try factory(checker)
        try:
            return factory_or_class(checker)
        except TypeError:
            # fallback: maybe it's a class/constructor that accepts no args
            try:
                return factory_or_class()
            except TypeError as e:
                raise TypeError(
                    f"Provider factory/class for model {llm_model} is not callable with (checker) or without args"
                ) from e

    async def get_non_streaming_response_from_streaming_response(  # noqa: C901
        self, llm_response: StreamingResponse
    ) -> NonStreamingResponse:
        non_streaming_content_blocks: List[ResponseData] = []

        current_content_block: Optional[ResponseData] = None
        text_buffer: str = ""

        for event in await llm_response.accumulated_events:
            if event.type == StreamingEventType.EXTENDED_THINKING_BLOCK_START:
                current_content_block = ExtendedThinkingData(
                    type=ContentBlockCategory.EXTENDED_THINKING, content=ExtendedThinkingContent(thinking="")
                )
            elif event.type == StreamingEventType.EXTENDED_THINKING_BLOCK_DELTA:
                if current_content_block and isinstance(current_content_block, ExtendedThinkingData):
                    current_content_block.content.thinking += event.content.thinking_delta
            elif event.type == StreamingEventType.EXTENDED_THINKING_BLOCK_END:
                if current_content_block and isinstance(current_content_block, ExtendedThinkingData):
                    current_content_block.content.signature = event.content.signature
                    non_streaming_content_blocks.append(current_content_block)
                    current_content_block = None
            elif event.type == StreamingEventType.REDACTED_THINKING:
                current_content_block = ExtendedThinkingData(
                    type=ContentBlockCategory.EXTENDED_THINKING,
                    content=ExtendedThinkingContent(type="redacted_thinking", thinking=event.data),
                )
                non_streaming_content_blocks.append(current_content_block)
                current_content_block = None

            elif event.type == StreamingEventType.TEXT_BLOCK_START:
                current_content_block = TextBlockData(
                    type=ContentBlockCategory.TEXT_BLOCK, content=TextBlockContent(text="")
                )
            elif event.type == StreamingEventType.TEXT_BLOCK_DELTA:
                if current_content_block and isinstance(current_content_block, TextBlockData):
                    current_content_block.content.text += event.content.text
            elif event.type == StreamingEventType.TEXT_BLOCK_END:
                if current_content_block and isinstance(current_content_block, TextBlockData):
                    non_streaming_content_blocks.append(current_content_block)
                    current_content_block = None
            elif event.type == StreamingEventType.TOOL_USE_REQUEST_START:
                current_content_block = ToolUseRequestData(
                    type=ContentBlockCategory.TOOL_USE_REQUEST,
                    content=ToolUseRequestContent(
                        tool_name=event.content.tool_name, tool_input={}, tool_use_id=event.content.tool_use_id
                    ),
                )
            elif event.type == StreamingEventType.TOOL_USE_REQUEST_DELTA:
                if current_content_block and isinstance(current_content_block, ToolUseRequestData):
                    text_buffer += event.content.input_params_json_delta
            elif event.type == StreamingEventType.TOOL_USE_REQUEST_END:
                if current_content_block and isinstance(current_content_block, ToolUseRequestData):
                    current_content_block.content.tool_input = json.loads(text_buffer if text_buffer else "{}")
                    non_streaming_content_blocks.append(current_content_block)
                    current_content_block = None
                    text_buffer = ""

        return NonStreamingResponse(
            type=LLMCallResponseTypes.NON_STREAMING,
            content=non_streaming_content_blocks,
            usage=await llm_response.usage,
            cost=await llm_response.cost if llm_response.cost else None,
        )

    async def store_llm_response_in_db(
        self,
        llm_response: UnparsedLLMCallResponse,
        session_id: int,
        prompt_type: str,
        prompt_category: str,
        llm_model: LLModels,
        query_id: int,
        call_chain_category: MessageCallChainCategory,
        previous_responses: List[MessageThreadDTO],
    ) -> NonStreamingResponse:
        response_to_use: NonStreamingResponse
        if llm_response.type == LLMCallResponseTypes.STREAMING:
            response_to_use = await self.get_non_streaming_response_from_streaming_response(llm_response)
        else:
            response_to_use = llm_response

        data_to_store: Sequence[ResponseData] = response_to_use.content
        data_hash = xxhash.xxh64(json.dumps([data.model_dump(mode="json") for data in data_to_store])).hexdigest()
        message_thread = MessageThreadData(
            session_id=session_id,
            actor=MessageThreadActor.ASSISTANT,
            query_id=query_id,
            message_type=MessageType.RESPONSE,
            conversation_chain=[message.id for message in previous_responses]
            + ([query_id] if query_id not in [message.id for message in previous_responses] else []),
            message_data=data_to_store,
            data_hash=data_hash,
            llm_model=llm_model,
            prompt_type=prompt_type,
            prompt_category=prompt_category,
            usage=response_to_use.usage,
            cost=response_to_use.cost,
            call_chain_category=call_chain_category,
        )
        await self.message_threads_repo.create_message_thread(message_thread)
        return response_to_use

    async def store_llm_query_in_db(
        self,
        session_id: int,
        previous_responses: List[MessageThreadDTO],
        prompt_type: str,
        prompt_category: str,
        llm_model: LLModels,
        prompt_rendered_messages: UserAndSystemMessages,
        prompt_vars: Dict[str, Any],
        call_chain_category: MessageCallChainCategory,
        attachmnts: Optional[List[Attachment]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MessageThreadDTO:
        """
        Store LLM query in DB

        Parameters:
            :param prompt: User and system messages
            :param session_id: Session id
            :param previous_responses: List of previous conversation messages

        Returns:
            :return: Message thread
        """
        full_user_message = (prompt_rendered_messages.cached_message or "") + prompt_rendered_messages.user_message
        data_hash = xxhash.xxh64(full_user_message).hexdigest()
        message_data: List[Union[FileBlockData, TextBlockData]] = [
            TextBlockData(
                type=ContentBlockCategory.TEXT_BLOCK,
                content=TextBlockContent(text=full_user_message),
                content_vars=prompt_vars if prompt_vars else None,
            )
        ]
        if attachmnts:
            for file in attachmnts:
                message_data.append(
                    FileBlockData(
                        type=ContentBlockCategory.FILE,
                        content=FileContent(attachment_id=file.attachment_id),
                    )
                )

        message_thread = MessageThreadData(
            session_id=session_id,
            actor=MessageThreadActor.USER,
            query_id=None,
            message_type=MessageType.QUERY,
            conversation_chain=[message.id for message in previous_responses],
            message_data=message_data,
            data_hash=data_hash,
            prompt_type=prompt_type,
            prompt_category=prompt_category,
            llm_model=llm_model,
            call_chain_category=call_chain_category,
            metadata=metadata,
        )
        return await self.message_threads_repo.create_message_thread(message_thread)

    async def parse_llm_response_data(
        self,
        llm_response: UnparsedLLMCallResponse,
        prompt_handler: BasePrompt,
        query_id: int,
        llm_response_storage_task: asyncio.Task[None],
    ) -> ParsedLLMCallResponse:
        if llm_response.type == LLMCallResponseTypes.STREAMING:
            parsed_stream = await prompt_handler.get_parsed_streaming_events(llm_response)
            return StreamingParsedLLMCallResponse(
                type=llm_response.type,
                content=llm_response.content,
                parsed_content=parsed_stream,
                usage=llm_response.usage,
                cost=llm_response.cost,
                model_used=prompt_handler.model_name,
                prompt_vars={},
                prompt_id=prompt_handler.prompt_type,
                accumulated_events=llm_response.accumulated_events,
                query_id=query_id,
                llm_response_storage_task=llm_response_storage_task,
            )
        else:
            parsed_content = prompt_handler.get_parsed_result(llm_response)
            return NonStreamingParsedLLMCallResponse(
                type=llm_response.type,
                content=llm_response.content,
                parsed_content=parsed_content,
                usage=llm_response.usage,
                cost=llm_response.cost,
                model_used=prompt_handler.model_name,
                prompt_vars={},
                prompt_id=prompt_handler.prompt_type,
                query_id=query_id,
            )


    # async def _get_attachment_data_task_map(
    #     self,
    #     previous_responses: List[MessageThreadDTO],
    #     current_attachments: List[Attachment],
    # ) -> Dict[int, asyncio.Task[ChatAttachmentDataWithObjectBytes]]:
    #     """
    #     map attachment id to attachment data fetch task
    #     """
    #
    #     previous_attachments: List[Attachment] = []
    #     for message in previous_responses:
    #         for data in message.message_data:
    #             if data.type == ContentBlockCategory.FILE:
    #                 result = await self.chat_attachments_repo.get_attachment_by_id(
    #                     attachment_id=data.content.attachment_id
    #                 )
    #                 if result and result.status == "deleted":
    #                     continue
    #                 previous_attachments.append(
    #                     Attachment(
    #                         attachment_id=data.content.attachment_id,
    #                     )
    #                 )
    #
    #     all_attachments = previous_attachments + current_attachments
    #
    #     return ChatFileUpload.get_attachment_data_task_map(all_attachments)

    async def fetch_and_parse_llm_response(  # noqa: C901
        self,
        client: BaseLLMProvider,
        session_id: int,
        prompt_type: str,
        llm_model: LLModels,
        query_id: int,
        prompt_handler: BasePrompt,
        call_chain_category: MessageCallChainCategory,
        reasoning: Optional[Reasoning] = None,
        tools: Optional[List[ConversationTool]] = None,
        tool_choice: Literal["none", "auto", "required"] = "auto",
        user_and_system_messages: Optional[UserAndSystemMessages] = None,
        tool_use_response: Optional[ToolUseResponseData] = None,
        previous_responses: List[MessageThreadDTO] = [],
        feedback: str = None,
        stream: bool = False,
        response_type: Optional[Literal["text", "json_object", "json_schema"]] = None,
        attachments: List[Attachment] = [],
        search_web: bool = False,
        checker: CancellationCheckerInterface = None,
        parallel_tool_calls: bool = False,
        text_format: Optional[Type[BaseModel]] = None,
        conversation_turns: List[UnifiedConversationTurn] = [],
    ) -> ParsedLLMCallResponse:
        """
        Fetch LLM response and parse it with retry logic

        Parameters:
            :param client: LLM provider client
            :param session_id: Session id
            :param prompt_type: Type of prompt
            :param llm_model: LLM model to use
            :param query_id: Query id
            :param prompt_handler: Prompt handler
            :param call_chain_category: Call chain category
            :param tools: List of tools
            :param user_and_system_messages: User and system messages
            :param tool_use_response: Tool use response
            :param previous_responses: List of previous responses
            :param max_retry: Maximum number of retries
            :param stream: Stream response
            :param response_type: Response type

        Returns:
            :return: Parsed LLM response
        """
        # check and get attachment data task map
        # attachment_data_task_map = await self._get_attachment_data_task_map(
        #     previous_responses=previous_responses,
        #     current_attachments=attachments,
        # )
        attachment_data_task_map = {}

        if not user_and_system_messages:
            user_and_system_messages = UserAndSystemMessages(system_message=prompt_handler.get_system_prompt())

        all_exceptions: List[Exception] = []
        max_retry = self.config.get_llm_max_retry()
        for i in range(0, max_retry):
            try:
                disable_caching = getattr(prompt_handler, "disable_caching", False)
                llm_payload = await client.build_llm_payload(
                    llm_model,
                    prompt=user_and_system_messages,
                    attachments=attachments,
                    tool_use_response=tool_use_response,
                    previous_responses=previous_responses,
                    tools=tools,
                    tool_choice=tool_choice,
                    cache_config=self.cache_config,
                    feedback=feedback,
                    attachment_data_task_map=attachment_data_task_map,
                    search_web=search_web,
                    disable_caching=disable_caching,
                    conversation_turns=conversation_turns,
                )

                # Validate token limit for the actual payload content
                await client.validate_token_limit_before_call(llm_payload, llm_model)

                if checker and checker.is_cancelled():
                    raise asyncio.CancelledError()
                llm_response = await client.call_service_client(
                    session_id=session_id,
                    llm_payload=llm_payload,
                    model=llm_model,
                    reasoning=reasoning,
                    stream=stream,
                    response_type=response_type,
                    parallel_tool_calls=parallel_tool_calls,
                    text_format=text_format,
                )

                # start task for storing LLM message in DB
                llm_response_storage_task = asyncio.create_task(
                    self.store_llm_response_in_db(
                        llm_response,
                        session_id,
                        prompt_type=prompt_type,
                        prompt_category=prompt_handler.prompt_category,
                        llm_model=llm_model,
                        query_id=query_id,
                        call_chain_category=call_chain_category,
                        previous_responses=previous_responses,
                    )
                )

                # if not streaming, ensure storage is done before sending response
                if not stream:
                    await llm_response_storage_task

                # Parse the LLM response
                parsed_response = await self.parse_llm_response_data(
                    llm_response=llm_response,
                    prompt_handler=prompt_handler,
                    query_id=query_id,
                    llm_response_storage_task=llm_response_storage_task,
                )
                return parsed_response
            except InputTokenLimitExceededError:
                # Don't retry for token limit exceeded, immediately raise
                raise
            except LLMThrottledError as e:
                AppLogger.log_warn(
                    f"LLM Throttled Error: {e}, retrying {i + 1}/{max_retry} after {e.retry_after} seconds"
                )
                raise
            except GeneratorExit:
                # Properly handle GeneratorExit exception when the coroutine is cancelled
                AppLogger.log_warn("LLM response generation was cancelled")
                raise  # Re-raise to properly propagate the exception
            except asyncio.CancelledError as e:
                all_exceptions.append(e)
                AppLogger.log_warn("LLM response task was cancelled")
                raise  # Re-raise to properly propagate cancellation
            except json.JSONDecodeError as e:
                all_exceptions.append(e)
                AppLogger.log_debug(traceback.format_exc())
                AppLogger.log_warn(f"Retry {i + 1}/{max_retry} JSON decode error: {e}")
            except ValueError as e:
                all_exceptions.append(e)
                AppLogger.log_debug(traceback.format_exc())
                AppLogger.log_warn(f"Retry {i + 1}/{max_retry} Parse error: {e}")
            except Exception as e:  # noqa: BLE001
                all_exceptions.append(e)
                AppLogger.log_debug(traceback.format_exc())
                AppLogger.log_warn(f"Retry {i + 1}/{max_retry} Error while fetching/parsing data from LLM: {e}")
            await asyncio.sleep(2)
        if all_exceptions:
            raise RetryException(
                f"Failed to get or parse response from LLM after {max_retry} retries - {all_exceptions[-1]}"
            ) from all_exceptions[-1]

    async def fetch_message_threads_from_conversation_turns(
        self,
        conversation_turns: List[ConversationTurn],
        session_id: int,
        prompt_handler: BasePrompt,
        call_chain_category: MessageCallChainCategory,
    ) -> List[MessageThreadDTO]:
        """
        Fetch message threads from conversation turns

        Parameters:
            :param conversation_turns: List of conversation turns

        Returns:
            :return: List of message threads
        """
        hashes_to_fetch: List[str] = []
        for turn in conversation_turns:
            if turn.content:
                hashes_to_fetch.append(xxhash.xxh64(str(turn.content)).hexdigest())

        db_message_threads = await self.message_threads_repo.get_message_threads_for_session(
            session_id=session_id, call_chain_category=call_chain_category
        )
        db_message_threads_hash_map: Dict[str, MessageThreadDTO] = {
            message.data_hash: message for message in db_message_threads
        }

        message_threads_to_insert: List[MessageThreadData] = []
        for turn, hash in zip(conversation_turns, hashes_to_fetch):
            if hash not in db_message_threads_hash_map:
                message_thread = MessageThreadData(
                    session_id=session_id,
                    actor=(
                        MessageThreadActor.USER if turn.role == ConversationRole.USER else MessageThreadActor.ASSISTANT
                    ),
                    query_id=None,
                    message_type=MessageType.RESPONSE,
                    conversation_chain=[],
                    data_hash=hash,
                    message_data=[],
                    prompt_type=prompt_handler.prompt_type,
                    prompt_category=prompt_handler.prompt_category,
                    llm_model=prompt_handler.model_name,
                    call_chain_category=call_chain_category,
                )
                message_threads_to_insert.append(message_thread)

        recently_inserted_message_threads_map: Dict[str, MessageThreadDTO] = {}
        if message_threads_to_insert:
            inserted_message_threads = await self.message_threads_repo.bulk_insert_message_threads(
                message_threads_to_insert
            )
            recently_inserted_message_threads_map: Dict[str, MessageThreadDTO] = {
                message.data_hash: message for message in inserted_message_threads
            }

        final_message_threads: List[MessageThreadDTO] = []
        for hash in hashes_to_fetch:
            final_message_threads.append(
                recently_inserted_message_threads_map[hash]
                if hash in recently_inserted_message_threads_map
                else db_message_threads_hash_map[hash]
            )

        return final_message_threads

    async def get_message_threads_from_message_thread_ids(
        self, message_thread_ids: List[int]
    ) -> List[MessageThreadDTO]:
        """
        Get message threads from message thread ids
        """

        if not message_thread_ids:
            return []

        db_message_threads = await self.message_threads_repo.get_message_threads_by_ids(
            message_thread_ids=message_thread_ids
        )
        return db_message_threads

    async def get_conversation_chain_messages(
        self,
        session_id: int,
        call_chain_category: MessageCallChainCategory,
        prompt_handler: BasePrompt,
        previous_responses: Union[List[int], List[ConversationTurn]] = [],
    ) -> List[MessageThreadDTO]:
        """
        Get conversation chain messages

        Parameters:
            :param session_id: Session id
            :param previous_responses: List of previous conversation messages (can be list of conversation turn or list of message ids)

        Returns:
            :return: List of conversation messages
        """
        # return empty list if no previous responses
        if not previous_responses:
            return []

        # determine the type of previous_responses, if it is list of conversation turns or list of message ids
        if all(isinstance(item, ConversationTurn) for item in previous_responses):
            return await self.fetch_message_threads_from_conversation_turns(
                conversation_turns=cast(List[ConversationTurn], previous_responses),
                session_id=session_id,
                prompt_handler=prompt_handler,
                call_chain_category=call_chain_category,
            )
        data = await self.get_message_threads_from_message_thread_ids(
            message_thread_ids=cast(List[int], previous_responses)
        )
        data.sort(key=lambda x: x.id)
        return data

    async def start_llm_query(
        self,
        session_id: int,
        prompt_feature: PromptFeatures,
        llm_model: LLModels,
        prompt_vars: Dict[str, Any],
        attachments: List[Attachment] = [],
        reasoning: Optional[Reasoning] = None,
        tools: Optional[List[ConversationTool]] = None,
        tool_choice: Literal["none", "auto", "required"] = "auto",
        previous_responses: List[int] = [],
        conversation_turns: List[UnifiedConversationTurn] = [],
        stream: bool = False,
        call_chain_category: MessageCallChainCategory = MessageCallChainCategory.CLIENT_CHAIN,
        search_web: bool = False,
        save_to_redis: bool = False,
        checker: Optional[CancellationCheckerInterface] = None,
        parallel_tool_calls: bool = False,
        prompt_handler_instance: Optional[BasePrompt] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ParsedLLMCallResponse:
        """
        Start LLM query

        Parameters:
            :param prompt_handler: Prompt handler
            :param tools: List of tools
            :param previous_responses: List of previous conversation messages (can be list of conversation turn or list of message ids)
            :param stream: Stream response

        Returns:
            :return: Parsed LLM response
        """

        prompt_handler = (
            prompt_handler_instance
            if prompt_handler_instance
            else self.prompt_handler_map.get_prompt(model_name=llm_model, feature=prompt_feature)(prompt_vars)
        )
        try:
            text_format = prompt_handler.get_text_format()
        except NotImplementedError:
            text_format = None

        if llm_model not in self.model_to_provider_class_map:
            raise ValueError(f"LLM model {llm_model} not supported")

        # client = self.model_to_provider_class_map[llm_model](checker=checker)
        client = self._get_provider(llm_model, checker=checker)
        user_and_system_messages = prompt_handler.get_prompt()

        conversation_chain_messages = await self.get_conversation_chain_messages(
            session_id=session_id,
            previous_responses=previous_responses,
            prompt_handler=prompt_handler,
            call_chain_category=call_chain_category,
        )

        prompt_thread = await self.store_llm_query_in_db(
            session_id=session_id,
            previous_responses=conversation_chain_messages,
            prompt_type=prompt_handler.prompt_type,
            prompt_category=prompt_handler.prompt_category,
            llm_model=prompt_handler.model_name,
            prompt_rendered_messages=user_and_system_messages,
            prompt_vars=prompt_vars,
            attachmnts=attachments,
            call_chain_category=call_chain_category,
            metadata=metadata,
        )
        if save_to_redis:
            await self.session_cache.set_session_query_id(prompt_thread.session_id, prompt_thread.id)
        return await self.fetch_and_parse_llm_response(
            client=client,
            session_id=session_id,
            prompt_type=prompt_handler.prompt_type,
            llm_model=prompt_handler.model_name,
            reasoning=reasoning,
            query_id=prompt_thread.id,
            prompt_handler=prompt_handler,
            call_chain_category=call_chain_category,
            tools=tools,
            tool_choice=tool_choice,
            user_and_system_messages=user_and_system_messages,
            attachments=attachments,
            previous_responses=conversation_chain_messages,
            stream=stream,
            response_type=prompt_handler.response_type,
            search_web=search_web,
            checker=checker,
            parallel_tool_calls=parallel_tool_calls,
            text_format=text_format,
            conversation_turns=conversation_turns,
        )

    async def get_token_count(self, content: str, llm_model: LLModels) -> int:
        provider = self.model_to_provider_class_map[llm_model]()
        return await provider.get_tokens(content=content, model=llm_model)
