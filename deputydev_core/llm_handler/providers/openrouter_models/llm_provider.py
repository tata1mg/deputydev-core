# TODO : REFACTOR: This file is long, needs refactoring.
import asyncio
import json
import uuid
from collections import defaultdict
from functools import reduce
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Type

from deputydev_core.services.tiktoken import TikToken
from deputydev_core.utils.app_logger import AppLogger
from openai.types import responses
from openai.types.chat import ChatCompletionChunk
from openai.types.responses import Response
from pydantic import BaseModel

from deputydev_core.llm_handler.models.dto.message_thread_dto import (
    ExtendedThinkingContent,
    LLModels,
    LLMUsage,
    MessageThreadActor,
    MessageThreadDTO,
    ResponseData,
    TextBlockContent,
    TextBlockData,
    ToolUseRequestContent,
    ToolUseRequestData,
    ToolUseResponseContent,
    ToolUseResponseData,
)
from deputydev_core.clients.openrouter.openrouter import OpenRouterServiceClient
from deputydev_core.llm_handler.services.chat_file_upload.dataclasses.chat_file_upload import (
    Attachment,
    ChatAttachmentDataWithObjectBytes,
)
from deputydev_core.llm_handler.utils.file_processor import get_base64_file_content
from deputydev_core.llm_handler.core.base_llm_provider import BaseLLMProvider
from deputydev_core.llm_handler.dataclasses.main import (
    ConversationRole,
    ConversationTool,
    LLMCallResponseTypes,
    NonStreamingResponse,
    PromptCacheConfig,
    StreamingEvent,
    StreamingEventType,
    StreamingResponse,
    TextBlockDelta,
    TextBlockDeltaContent,
    TextBlockEnd,
    TextBlockStart,
    ToolUseRequestDelta,
    ToolUseRequestDeltaContent,
    ToolUseRequestEnd,
    ToolUseRequestStart,
    ToolUseRequestStartContent,
    UnparsedLLMCallResponse,
    UserAndSystemMessages,
)
from deputydev_core.llm_handler.dataclasses.unified_conversation_turn import UnifiedConversationTurn
from deputydev_core.llm_handler.interfaces.cancellation_interface import CancellationCheckerInterface
from deputydev_core.llm_handler.interfaces.caches_interface import SessionCacheInterface
from deputydev_core.llm_handler.dataclasses.main import Reasoning


class OpenRouter(BaseLLMProvider):
    def __init__(
        self, config: Dict, session_cache: SessionCacheInterface, checker: Optional[CancellationCheckerInterface] = None
    ) -> None:
        super().__init__(config, session_cache, checker=checker)
        self._active_streams: Dict[str, AsyncIterator] = {}
        self.anthropic_client = None

    def _initialize_client(self):
        """Initialize OpenAI client with injected config"""
        if not self.config:
            raise ValueError("OpenAI configuration not provided")

        openrouter_config = self.config.get("OPENROUTER", {})
        self.client = OpenRouterServiceClient(config=openrouter_config)

    async def build_llm_payload(  # noqa: C901
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
        """XP
        Formats the conversation for OpenRouter's GPT model.

        Args:
            prompt (Dict[str, str]): A prompt object.
            previous_responses (List[Dict[str, str]] ): previous messages to pass to LLM

        Returns:
            List[Dict[str, str]]: A formatted list of message dictionaries.
        """
        model_config = self._get_model_config(llm_model)
        formatted_tools: List[Dict[str, Any]] = []
        if tools:
            for tool in tools:
                func_tool = responses.FunctionToolParam(
                    name=tool.name,
                    parameters=tool.input_schema.model_dump(mode="json", exclude_unset=True, by_alias=True)
                    if tool.input_schema.properties
                    else None,
                    description=tool.description,
                    type="function",
                    strict=False,
                )
                formatted_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": func_tool["name"],
                            "description": func_tool.get("description"),
                            "parameters": func_tool["parameters"],
                        },
                    }
                )
            formatted_tools.sort(key=lambda t: t["function"]["name"])
            tool_choice = tool_choice if tool_choice else "auto"

        messages: List[Dict[str, Any]] = []

        # system
        if prompt and prompt.system_message and not conversation_turns:
            messages.append({"role": "system", "content": prompt.system_message})

        if previous_responses and not conversation_turns:
            messages.extend(await self.get_conversation_turns(previous_responses, attachment_data_task_map))
        # user
        if prompt and prompt.user_message and not conversation_turns:
            # collect any image attachments
            image_parts: List[Dict[str, Any]] = []
            for attachment in attachments:
                if attachment.attachment_id not in attachment_data_task_map:
                    continue
                attachment_data = await attachment_data_task_map[attachment.attachment_id]
                if not attachment_data.attachment_metadata.file_type.startswith("image/"):
                    continue

                data_url = (
                    f"data:{attachment_data.attachment_metadata.file_type};"
                    f"base64,{get_base64_file_content(attachment_data.object_bytes)}"
                )
                image_parts.append({"type": "image_url", "image_url": {"url": data_url}})

            # if we have images, send a multipart content array, else just the string
            if image_parts:
                user_parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt.user_message}] + image_parts
                messages.append({"role": "user", "content": user_parts})
            else:
                messages.append({"role": "user", "content": prompt.user_message})

        if tool_use_response and not conversation_turns:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_use_response.content.tool_use_id,
                    "name": tool_use_response.content.tool_name,
                    "content": json.dumps(tool_use_response.content.response),
                }
            )
        messages = self.filter_empty_assistant_messages(messages)
        return {
            "model": model_config["NAME"],
            "tool_choice": tool_choice,
            "max_tokens": model_config["MAX_TOKENS"],
            "messages": messages,
            "tools": formatted_tools,
        }

    async def get_conversation_turns(  # noqa: C901
        self,
        previous_responses: List[MessageThreadDTO],
        attachment_data_task_map: Dict[int, asyncio.Task[ChatAttachmentDataWithObjectBytes]],
    ) -> List[Dict[str, Any]]:
        """
        Turn our internal MessageThreadDTOs into OpenRouter‐style messages:
        - plain text → {role, content: str}
        - prior function calls → {role:assistant, content:None, tool_calls:[…]}
        - tool outputs      → {role:tool, tool_call_id, name, content: str}
        - prior images      → {role:user, content:[{type:"image_url",image_url:{url:…}}]}
        """
        conversation_turns: List[Dict[str, Any]] = []

        for message in previous_responses:
            role = ConversationRole.USER if message.actor == MessageThreadActor.USER else ConversationRole.ASSISTANT
            message_datas = list(message.message_data)
            pending_tool_calls: List[Dict[str, Any]] = []

            def flush_tool_calls() -> None:
                nonlocal pending_tool_calls
                if pending_tool_calls:
                    conversation_turns.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": pending_tool_calls,
                        }
                    )
                    pending_tool_calls = []

            for message_data in message_datas:
                content_data = message_data.content

                # Ignore extended thinking entirely and DO NOT flush here
                if isinstance(content_data, ExtendedThinkingContent):
                    continue

                # 1) Collect assistant tool use requests (supports parallel tool calls)
                if role == ConversationRole.ASSISTANT and isinstance(content_data, ToolUseRequestContent):
                    pending_tool_calls.append(
                        {
                            "id": content_data.tool_use_id,
                            "type": "function",
                            "function": {
                                "name": content_data.tool_name,
                                "arguments": json.dumps(content_data.tool_input),
                            },
                        }
                    )
                    continue  # keep collecting consecutive ToolUseRequestContent

                # Anything else: first flush any pending tool calls to preserve order
                flush_tool_calls()

                # 2) Plain text
                if isinstance(content_data, TextBlockContent):
                    conversation_turns.append({"role": role.value, "content": content_data.text})

                # 3) Embedded images (earlier user turns)
                elif hasattr(content_data, "attachment_id"):
                    attachment_id = content_data.attachment_id
                    if attachment_id not in attachment_data_task_map:
                        continue
                    attachment_data = await attachment_data_task_map[attachment_id]
                    if attachment_data.attachment_metadata.file_type.startswith("image/"):
                        data_url = (
                            f"data:{attachment_data.attachment_metadata.file_type};"
                            f"base64,{get_base64_file_content(attachment_data.object_bytes)}"
                        )
                        conversation_turns.append(
                            {
                                "role": "user",
                                "content": [{"type": "image_url", "image_url": {"url": data_url}}],
                            }
                        )

                # 4) Tool outputs (responses)
                elif isinstance(content_data, ToolUseResponseContent):
                    conversation_turns.append(
                        {
                            "role": "tool",
                            "tool_call_id": content_data.tool_use_id,
                            "name": content_data.tool_name,
                            "content": json.dumps(content_data.response),
                        }
                    )

                # (else: silently ignore unknown content types)

            # End of this message: flush any remaining parallel tool calls
            flush_tool_calls()

        return conversation_turns

    def _parse_non_streaming_response(self, response: Response) -> NonStreamingResponse:
        """
        Parses the response from OpenRouter's GPT model.

        Args:
            response : The raw response from the GPT model.

        Returns:
            NonStreamingResponse: Parsed response
        """
        non_streaming_content_blocks: List[ResponseData] = []
        for block in response.output:
            if block.type == "message":
                non_streaming_content_blocks.append(TextBlockData(content=TextBlockContent(text=response.output_text)))
            if block.type == "function_call":
                non_streaming_content_blocks.append(
                    ToolUseRequestData(
                        content=ToolUseRequestContent(
                            tool_input=json.loads(block.arguments),
                            tool_name=block.name,
                            tool_use_id=block.call_id,
                        )
                    )
                )

        return NonStreamingResponse(
            content=non_streaming_content_blocks,
            usage=(
                LLMUsage(
                    input=response.usage.input_tokens - response.usage.input_tokens_details.cached_tokens,
                    output=response.usage.output_tokens,
                    cache_read=response.usage.input_tokens_details.cached_tokens,
                )
                if response.usage
                else LLMUsage(input=0, output=0)
            ),
        )

    def filter_empty_assistant_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Removes empty assistant messages (content None or empty string)
        immediately after an assistant message with tool_calls.
        """
        filtered: List[Dict[str, Any]] = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "assistant" and (msg.get("content") is None or str(msg.get("content")).strip() == ""):
                if i > 0 and messages[i - 1].get("role") == "assistant" and messages[i - 1].get("tool_calls"):
                    continue  # skip this empty assistant message
            filtered.append(msg)
        return filtered

    async def call_service_client(
        self,
        session_id: int,
        llm_payload: Dict[str, Any],
        model: LLModels,
        stream: bool = False,
        response_type: Optional[Literal["text", "json_object", "json_schema"]] = None,
        parallel_tool_calls: bool = False,
        text_format: Optional[Type[BaseModel]] = None,
        reasoning: Optional[Reasoning] = None,
    ) -> UnparsedLLMCallResponse:
        """
        Calls the OpenRouter service client.

        Args:
            messages (List[Dict[str, str]]): Formatted conversation messages.

        Returns:
            str: The response from the GPT model.
        """
        model_config = self._get_model_config(model)
        stream_id = str(uuid.uuid4())
        if stream:
            response = await OpenRouterServiceClient().get_llm_stream_response(
                model=model_config["NAME"],
                max_tokens=model_config["MAX_TOKENS"],
                temperature=model_config["TEMPERATURE"],
                messages=llm_payload["messages"],
                tools=llm_payload["tools"],
                tool_choice=llm_payload["tool_choice"],
                reasoning=reasoning,
                provider=model_config.get("PROVIDER", None),
                response_format=response_type,
                structured_outputs=llm_payload.get("structured_outputs", None),
                parallel_tool_calls=parallel_tool_calls,
                session_id=session_id,
            )
            return await self._parse_streaming_response(response, stream_id, session_id, model_config)
        else:
            response = await OpenRouterServiceClient().get_llm_non_stream_response(
                model=model_config["NAME"],
                max_tokens=model_config["MAX_TOKENS"],
                temperature=model_config["TEMPERATURE"],
                conversation_messages=llm_payload["conversation_messages"],
                tools=llm_payload["tools"],
                tool_choice=llm_payload["tool_choice"],
                reasoning=model_config["REASONING"],
                provider=model_config["PROVIDER"],
                response_format=response_type,
                structured_outputs=llm_payload["structured_outputs"],
                parallel_tool_calls=parallel_tool_calls,
                session_id=session_id,
            )
            return self._parse_non_streaming_response(response)

    async def _parse_streaming_response(  # noqa: C901
        self,
        response: AsyncIterator[ChatCompletionChunk],
        stream_id: Optional[str] = None,
        session_id: Optional[int] = None,
        model_config: Dict[str, Any] = {},
    ) -> StreamingResponse:
        stream_id = stream_id or str(uuid.uuid4())
        usage = LLMUsage(input=0, output=0, cache_read=0, cache_write=None)
        streaming_completed = asyncio.Event()
        accumulated_events: List[StreamingEvent] = []
        streaming_cost: Optional[float] = None

        async def stream_content() -> AsyncIterator[StreamingEvent]:  # noqa: C901
            nonlocal usage, streaming_completed, accumulated_events, streaming_cost, session_id
            self._active_streams[stream_id] = response

            buffer: List[StreamingEvent] = []
            non_combinable_types = {TextBlockStart, TextBlockEnd, ToolUseRequestStart, ToolUseRequestEnd}
            batch_size = model_config.get("STREAM_BATCH_SIZE", 1)

            tool_usage_state: dict[str, bool] = defaultdict(bool)
            current_tool_id: Optional[str] = None
            current_tool_name: Optional[str] = None
            text_block_open = False

            try:
                async for chunk in response:
                    # Cancellation check
                    if self.checker and self.checker.is_cancelled() and self.session_cache:
                        await self.session_cache.cleanup_session_data(session_id)
                        raise asyncio.CancelledError()

                    # Usage and cost handling
                    if chunk.usage:
                        details = chunk.usage.prompt_tokens_details
                        cached_tokens = getattr(details, "cached_tokens", 0) if details else 0
                        prompt_tokens = chunk.usage.prompt_tokens or 0
                        completion_tokens = chunk.usage.completion_tokens or 0
                        usage += LLMUsage(
                            input=prompt_tokens - cached_tokens, output=completion_tokens, cache_read=cached_tokens
                        )
                        if chunk.usage.cost is not None:
                            streaming_cost = chunk.usage.cost
                        continue

                    delta = chunk.choices[0].delta or {}
                    finish_reason = chunk.choices[0].finish_reason
                    text_part = delta.content or ""
                    tool_calls = getattr(delta, "tool_calls", []) or []

                    # Tool-call event handling
                    if tool_calls:
                        if text_block_open:
                            if buffer:
                                yield reduce(lambda a, b: a + b, buffer)
                                buffer.clear()
                            end_event = TextBlockEnd(type=StreamingEventType.TEXT_BLOCK_END)
                            accumulated_events.append(end_event)
                            yield end_event
                            text_block_open = False

                        for tool_call in tool_calls:
                            tool_id = tool_call.id or current_tool_id
                            tool_name = tool_call.function.name or current_tool_name
                            arguments = tool_call.function.arguments or ""

                            if tool_call.id and tool_call.function.name:
                                if current_tool_id and tool_usage_state[current_tool_id]:
                                    end_event = ToolUseRequestEnd(type=StreamingEventType.TOOL_USE_REQUEST_END)
                                    accumulated_events.append(end_event)
                                    yield end_event
                                    tool_usage_state[current_tool_id] = False

                                current_tool_id, current_tool_name = tool_id, tool_name
                                start_event = ToolUseRequestStart(
                                    type=StreamingEventType.TOOL_USE_REQUEST_START,
                                    content=ToolUseRequestStartContent(
                                        tool_name=current_tool_name, tool_use_id=current_tool_id
                                    ),
                                )
                                accumulated_events.append(start_event)
                                yield start_event
                                tool_usage_state[current_tool_id] = True

                            if arguments and current_tool_id and tool_usage_state[current_tool_id]:
                                delta_event = ToolUseRequestDelta(
                                    type=StreamingEventType.TOOL_USE_REQUEST_DELTA,
                                    content=ToolUseRequestDeltaContent(input_params_json_delta=arguments),
                                )
                                accumulated_events.append(delta_event)
                                yield delta_event

                        if finish_reason == "tool_calls" and current_tool_id and tool_usage_state[current_tool_id]:
                            end_event = ToolUseRequestEnd(type=StreamingEventType.TOOL_USE_REQUEST_END)
                            accumulated_events.append(end_event)
                            yield end_event
                            tool_usage_state[current_tool_id] = False
                            current_tool_id = current_tool_name = None

                        continue

                    # If switching from tool-call to text
                    if current_tool_id and tool_usage_state[current_tool_id]:
                        end_event = ToolUseRequestEnd(type=StreamingEventType.TOOL_USE_REQUEST_END)
                        accumulated_events.append(end_event)
                        yield end_event
                        tool_usage_state[current_tool_id] = False
                        current_tool_id = current_tool_name = None

                    # Text block streaming
                    if text_part and not text_block_open:
                        start_event = TextBlockStart(type=StreamingEventType.TEXT_BLOCK_START)
                        if buffer:
                            yield reduce(lambda a, b: a + b, buffer)
                            buffer.clear()
                        accumulated_events.append(start_event)
                        text_block_open = True
                        yield start_event

                    if text_part:
                        delta_event = TextBlockDelta(
                            type=StreamingEventType.TEXT_BLOCK_DELTA,
                            content=TextBlockDeltaContent(text=text_part),
                        )
                        accumulated_events.append(delta_event)
                        if buffer and (type(buffer[0]) in non_combinable_types or len(buffer) >= batch_size):
                            yield reduce(lambda a, b: a + b, buffer)
                            buffer.clear()
                        buffer.append(delta_event)

                    # End text block on "stop"
                    if finish_reason == "stop" and text_block_open:
                        if buffer:
                            yield reduce(lambda a, b: a + b, buffer)
                            buffer.clear()
                        end_event = TextBlockEnd(type=StreamingEventType.TEXT_BLOCK_END)
                        accumulated_events.append(end_event)
                        yield end_event
                        text_block_open = False

                # Stream cleanup
                if text_block_open:
                    if buffer:
                        yield reduce(lambda a, b: a + b, buffer)
                        buffer.clear()
                    end_event = TextBlockEnd(type=StreamingEventType.TEXT_BLOCK_END)
                    accumulated_events.append(end_event)
                    yield end_event

                if current_tool_id and tool_usage_state[current_tool_id]:
                    end_event = ToolUseRequestEnd(type=StreamingEventType.TOOL_USE_REQUEST_END)
                    accumulated_events.append(end_event)
                    yield end_event

            finally:
                streaming_completed.set()

        async def get_usage() -> LLMUsage:
            await streaming_completed.wait()
            return usage

        async def get_cost() -> Optional[float]:
            await streaming_completed.wait()
            return streaming_cost

        async def get_accumulated_events() -> List[StreamingEvent]:
            await streaming_completed.wait()
            return accumulated_events

        return StreamingResponse(
            content=stream_content(),
            usage=asyncio.create_task(get_usage()),
            cost=asyncio.create_task(get_cost()),
            type=LLMCallResponseTypes.STREAMING,
            accumulated_events=asyncio.create_task(get_accumulated_events()),
        )

    async def get_tokens(self, content: str, model: LLModels) -> int:
        return TikToken().count(text=content)

    def _extract_payload_content_for_token_counting(self, llm_payload: Dict[str, Any]) -> str:  # noqa : C901
        """
        Extract the relevant content from LLM payload that will be sent to the LLM for token counting.
        This handles OpenRouter's payload structure and includes handling for multipart content and attachments.
        """
        content_parts = []

        try:
            # OpenRouter structure: messages
            if "messages" in llm_payload:
                for message in llm_payload["messages"]:
                    if isinstance(message, dict):
                        # If message has 'content', check if it's a string or a list (multipart content)
                        if "content" in message:
                            if isinstance(message["content"], str):
                                content_parts.append(message["content"])
                            elif isinstance(message["content"], list):
                                # Iterate through multipart content, which may include text and image parts
                                for content in message["content"]:
                                    if isinstance(content, dict):
                                        # For text parts
                                        if content.get("type") == "text":
                                            content_parts.append(content.get("text", ""))
                                        # For image URL parts (base64 encoded)
                                        elif content.get("type") == "image_url":
                                            content_parts.append(content.get("image_url", {}).get("url", ""))
                        # If it's a tool response message, append the tool output
                        elif message.get("type") == "function_call_output" and "output" in message:
                            content_parts.append(str(message["output"]))

            # Include tools information for token counting if present
            if "tools" in llm_payload and llm_payload["tools"]:
                try:
                    tools_content = json.dumps(llm_payload["tools"])
                    content_parts.append(tools_content)
                except Exception as e:  # noqa : BLE001
                    AppLogger.log_warn(f"Error processing tools for token counting: {e}")
                    # Skip tools if they can't be processed
                    pass

        except Exception as e:  # noqa : BLE001
            AppLogger.log_warn(f"Error extracting payload content for token counting: {e}")
            # Fallback: return a simple placeholder instead of trying to serialize non-serializable objects
            return "Unable to extract content for token counting"

        return "\n".join(content_parts)
