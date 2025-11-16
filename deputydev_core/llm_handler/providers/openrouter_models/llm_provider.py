# TODO : REFACTOR: This file is long, needs refactoring.
import asyncio
import base64
import json
import uuid
from collections import defaultdict
from functools import reduce
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Type

from openai.types import responses
from openai.types.chat import ChatCompletionChunk
from openai.types.responses import Response
from pydantic import BaseModel

from deputydev_core.clients.openrouter.openrouter import OpenRouterServiceClient
from deputydev_core.llm_handler.core.base_llm_provider import BaseLLMProvider
from deputydev_core.llm_handler.dataclasses.main import (
    ConversationTool,
    ExtendedThinkingBlockDelta,
    ExtendedThinkingBlockDeltaContent,
    ExtendedThinkingBlockEnd,
    ExtendedThinkingBlockEndContent,
    ExtendedThinkingBlockStart,
    LLMCallResponseTypes,
    NonStreamingResponse,
    PromptCacheConfig,
    Reasoning,
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
from deputydev_core.llm_handler.dataclasses.unified_conversation_turn import (
    AssistantConversationTurn,
    ToolConversationTurn,
    UnifiedConversationTurn,
    UnifiedTextConversationTurnContent,
    UnifiedToolRequestConversationTurnContent,
    UserConversationTurn,
)
from deputydev_core.llm_handler.interfaces.cancellation_interface import CancellationCheckerInterface
from deputydev_core.llm_handler.models.dto.message_thread_dto import (
    LLModels,
    LLMUsage,
    MessageThreadDTO,
    ResponseData,
    TextBlockContent,
    TextBlockData,
    ToolUseRequestContent,
    ToolUseRequestData,
    ToolUseResponseData,
)
from deputydev_core.llm_handler.services.chat_file_upload.dataclasses.chat_file_upload import (
    Attachment,
    ChatAttachmentDataWithObjectBytes,
)
from deputydev_core.services.tiktoken import TikToken
from deputydev_core.utils.app_logger import AppLogger


class OpenRouter(BaseLLMProvider):
    def __init__(self, config: Dict, checker: Optional[CancellationCheckerInterface] = None) -> None:
        super().__init__(config, checker=checker)
        self._active_streams: Dict[str, AsyncIterator] = {}
        self.client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize OpenAI client with injected config"""
        if not self.config:
            raise ValueError("OpenRouter configuration not provided")

        openrouter_config = self.config.get("OPENROUTER", {})
        self.client = OpenRouterServiceClient(config=openrouter_config)

    def _image_content_to_data_url(self, bytes_data: bytes, mimetype: str) -> str:
        b64 = base64.b64encode(bytes_data).decode("utf-8")
        return f"data:{mimetype};base64,{b64}"

    def _openrouter_messages_from_user_turn(self, turn: UserConversationTurn) -> List[Dict[str, Any]]:
        texts: List[str] = []
        image_parts: List[Dict[str, Any]] = []

        for c in turn.content:
            if isinstance(c, UnifiedTextConversationTurnContent):
                texts.append(c.text)
            else:
                data_url = self._image_content_to_data_url(c.bytes_data, c.image_mimetype)
                image_parts.append({"type": "image_url", "image_url": {"url": data_url}})

        if not texts and not image_parts:
            return []

        # Only text → plain string content (backward compatible)
        if texts and not image_parts:
            return [{"role": "user", "content": "\n\n".join(texts)}]

        # Only images → array of image parts
        if image_parts and not texts:
            return [{"role": "user", "content": image_parts}]

        # Mixed → multipart with text then images
        parts: List[Dict[str, Any]] = [{"type": "text", "text": "\n\n".join(texts)}] + image_parts
        return [{"role": "user", "content": parts}]

    def _flush_pending_tool_calls(self, pending_tool_calls: List[Dict[str, Any]], out: List[Dict[str, Any]]) -> None:
        if pending_tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": None,
                    # copy the list (and its dict items) so later .clear() doesn't mutate the message
                    "tool_calls": [tc.copy() for tc in pending_tool_calls],
                }
            )
            pending_tool_calls.clear()

    def _openrouter_messages_from_assistant_turn(self, turn: AssistantConversationTurn) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        pending_tool_calls: List[Dict[str, Any]] = []

        for c in turn.content:
            if isinstance(c, UnifiedToolRequestConversationTurnContent):
                pending_tool_calls.append(
                    {
                        "id": c.tool_use_id,
                        "type": "function",
                        "function": {
                            "name": c.tool_name,
                            "arguments": json.dumps(c.tool_input),
                        },
                    }
                )
            else:  # UnifiedTextConversationTurnContent
                # Any text breaks parallel tool-call grouping
                self._flush_pending_tool_calls(pending_tool_calls, out)
                out.append({"role": "assistant", "content": c.text})

        # End: flush remaining parallel calls
        self._flush_pending_tool_calls(pending_tool_calls, out)
        return out

    def _openrouter_messages_from_tool_turn(self, turn: ToolConversationTurn) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for c in turn.content:
            # Map each tool response to a tool message (OpenRouter format)
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": c.tool_use_id,
                    "name": c.tool_name,
                    "content": json.dumps(c.tool_use_response),
                }
            )
        return out

    def _get_openrouter_messages_from_conversation_turns(
        self,
        conversation_turns: List[UnifiedConversationTurn],
        system_message: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Convert UnifiedConversationTurn → OpenRouter-style messages[].
        Keeps your legacy message schema intact.
        """
        messages: List[Dict[str, Any]] = []

        # Preserve prior behavior: include system if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        for turn in conversation_turns:
            if isinstance(turn, UserConversationTurn):
                messages.extend(self._openrouter_messages_from_user_turn(turn))
            elif isinstance(turn, AssistantConversationTurn):
                messages.extend(self._openrouter_messages_from_assistant_turn(turn))
            else:  # ToolConversationTurn
                messages.extend(self._openrouter_messages_from_tool_turn(turn))

        return messages

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
            conversation_turns (List[UnifiedConversationTurn]): previous messages to pass to LLM

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
                            "parameters": func_tool["parameters"]
                            if func_tool.get("parameters")
                            else {"type": "object", "properties": {}},
                        },
                    }
                )
            formatted_tools.sort(key=lambda t: t["function"]["name"])
            tool_choice = tool_choice if tool_choice else "auto"

        # Messages
        messages: List[Dict[str, Any]] = []

        sys_msg = prompt.system_message if (prompt and prompt.system_message) else None
        messages = self._get_openrouter_messages_from_conversation_turns(
            conversation_turns=conversation_turns,
            system_message=sys_msg,
        )
        messages = self.filter_empty_assistant_messages(messages)
        return {
            "model": model_config["NAME"],
            "tool_choice": tool_choice,
            "max_tokens": model_config["MAX_TOKENS"],
            "messages": messages,
            "tools": formatted_tools,
        }

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
            response = await self.client.get_llm_stream_response(
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
            response = await self.client.get_llm_non_stream_response(
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
            extended_thinking_open = False
            tool_call_seen = False

            try:
                async for chunk in response:
                    # Cancellation check
                    if self.checker:
                        await self.checker.enforce_cancellation_with_cleanup()

                    # Usage and cost handling
                    if chunk.usage:
                        details = chunk.usage.prompt_tokens_details
                        cached_tokens = getattr(details, "cached_tokens", 0) if details else 0
                        prompt_tokens = chunk.usage.prompt_tokens or 0
                        completion_tokens = chunk.usage.completion_tokens or 0
                        usage += LLMUsage(
                            input=prompt_tokens - cached_tokens,
                            output=completion_tokens,
                            cache_read=cached_tokens,
                        )
                        if chunk.usage.cost is not None:
                            streaming_cost = chunk.usage.cost
                        continue

                    delta = chunk.choices[0].delta or {}
                    finish_reason = chunk.choices[0].finish_reason
                    text_part = delta.content or ""
                    tool_calls = getattr(delta, "tool_calls", []) or []
                    reasoning_text = getattr(delta, "reasoning", None)
                    reasoning_details = getattr(delta, "reasoning_details", None)

                    # --- Extended Thinking Handling ---
                    # Normalize encrypted reasoning: always ignore encrypted chunks
                    if reasoning_details:
                        if isinstance(reasoning_details, dict):
                            reasoning_dict: Dict[str, Any] = reasoning_details
                            if reasoning_dict.get("type") == "reasoning.encrypted":
                                continue
                        elif isinstance(reasoning_details, list):
                            reasoning_list: List[Dict[str, Any]] = [d for d in reasoning_details if isinstance(d, dict)]
                            if any(d.get("type") == "reasoning.encrypted" for d in reasoning_list):
                                continue

                    if reasoning_text or reasoning_details:
                        # After first tool-call, ignore all reasoning
                        if tool_call_seen:
                            continue

                        if not extended_thinking_open:
                            start_event = ExtendedThinkingBlockStart()
                            accumulated_events.append(start_event)
                            yield start_event
                            extended_thinking_open = True

                        # Normalize reasoning_details into a list of dicts
                        details_list: List[Dict[str, Any]] = []
                        if reasoning_details:
                            if isinstance(reasoning_details, dict):
                                details_list = [reasoning_details]
                            elif isinstance(reasoning_details, list):
                                details_list = [d for d in reasoning_details if isinstance(d, dict)]

                        # Prefer reasoning_text, else join summaries or data fields
                        thinking_delta: str = reasoning_text or " ".join(
                            str(d.get("summary") or d.get("data") or "") for d in details_list
                        )

                        delta_event = ExtendedThinkingBlockDelta(
                            type=StreamingEventType.EXTENDED_THINKING_BLOCK_DELTA,
                            content=ExtendedThinkingBlockDeltaContent(thinking_delta=thinking_delta),
                        )
                        accumulated_events.append(delta_event)
                        yield delta_event
                        continue  # don’t drop into text/tool flow

                    # If reasoning was open and now we see text/tool/stop → close it
                    if extended_thinking_open and (text_part or tool_calls or finish_reason in {"stop", "tool_calls"}):
                        end_event = ExtendedThinkingBlockEnd(
                            type=StreamingEventType.EXTENDED_THINKING_BLOCK_END,
                            content=ExtendedThinkingBlockEndContent(signature=""),
                        )
                        accumulated_events.append(end_event)
                        yield end_event
                        extended_thinking_open = False

                    # --- Tool-call event handling ---
                    if tool_calls:
                        tool_call_seen = True  # from now on, no text/reasoning is used

                        # Close any active text block before tool calls
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
                                # If a previous tool call is still open, end it
                                if current_tool_id and tool_usage_state[current_tool_id]:
                                    end_event = ToolUseRequestEnd(type=StreamingEventType.TOOL_USE_REQUEST_END)
                                    accumulated_events.append(end_event)
                                    yield end_event
                                    tool_usage_state[current_tool_id] = False

                                current_tool_id, current_tool_name = tool_id, tool_name
                                start_event = ToolUseRequestStart(
                                    type=StreamingEventType.TOOL_USE_REQUEST_START,
                                    content=ToolUseRequestStartContent(
                                        tool_name=current_tool_name,
                                        tool_use_id=current_tool_id,
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

                        continue  # don’t drop into text flow

                    # If switching from tool-call to text:
                    # With your new semantics, text after tool calls is ignored anyway,
                    # but we still want to close any dangling tool state if that happens.
                    if current_tool_id and tool_usage_state[current_tool_id] and text_part:
                        end_event = ToolUseRequestEnd(type=StreamingEventType.TOOL_USE_REQUEST_END)
                        accumulated_events.append(end_event)
                        yield end_event
                        tool_usage_state[current_tool_id] = False
                        current_tool_id = current_tool_name = None
                        # text will be handled by logic below (or ignored if tool_call_seen True)

                    # --- Text block streaming ---
                    # After first tool call: ignore ALL text completely
                    if tool_call_seen and text_part:
                        continue

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
                        # batching for text deltas
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

                # --- Stream cleanup ---
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
