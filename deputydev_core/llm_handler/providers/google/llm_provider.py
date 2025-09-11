import asyncio
import json
import uuid
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Tuple, Type

from google.genai import types as google_genai_types
from pydantic import BaseModel

from deputydev_core.clients.gemini.gemini import GeminiServiceClient
from deputydev_core.llm_handler.core.base_llm_provider import BaseLLMProvider
from deputydev_core.llm_handler.dataclasses.main import (
    ConversationRoleGemini,
    ConversationTool,
    LLMCallResponseTypes,
    MalformedToolUseRequest,
    MalformedToolUseRequestContent,
    NonStreamingResponse,
    PromptCacheConfig,
    Reasoning,
    StreamingEvent,
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
    UnifiedImageConversationTurnContent,
    UnifiedTextConversationTurnContent,
    UnifiedToolRequestConversationTurnContent,
    UserConversationTurn,
)
from deputydev_core.llm_handler.interfaces.cancellation_interface import CancellationCheckerInterface
from deputydev_core.llm_handler.models.dto.message_thread_dto import (
    ContentBlockCategory,
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
from deputydev_core.llm_handler.services.chat_file_upload.dataclasses.chat_file_upload import (
    Attachment,
    ChatAttachmentDataWithObjectBytes,
)
from deputydev_core.utils.app_logger import AppLogger


class Google(BaseLLMProvider):
    def __init__(self, config: Dict, checker: Optional[CancellationCheckerInterface] = None) -> None:
        super().__init__(config, checker=checker)
        self._active_streams: Dict[str, AsyncIterator] = {}
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Gemini client with injected config"""
        vertex_config = self.config.get("VERTEX", {})
        self.client = GeminiServiceClient(vertex_config)

    async def get_conversation_turns(  # noqa: C901
        self,
        previous_responses: List[MessageThreadDTO],
        attachment_data_task_map: Dict[int, asyncio.Task[ChatAttachmentDataWithObjectBytes]],
    ) -> List[google_genai_types.Content]:
        """
        Formats the conversation history for Google's Gemini model.

        Args:
            previous_responses (List[MessageThreadDTO]): The previous conversation turns.

        Returns:
            List[Content]: The formatted conversation history for Gemini.
        """
        conversation_turns: List[google_genai_types.Content] = []
        tool_requests: Dict[str, ToolUseRequestContent] = {}
        tool_requests_order: List[str] = []

        for message in previous_responses:
            role = (
                ConversationRoleGemini.USER.value
                if message.actor == MessageThreadActor.USER
                else ConversationRoleGemini.MODEL.value
            )
            parts: List[google_genai_types.Part] = []

            # Sort: TextBlockData first, then tool-related
            message_datas = list(message.message_data)
            message_datas.sort(key=lambda x: 0 if isinstance(x, TextBlockData) else 1)

            for message_data in message_datas:
                content_data = message_data.content

                if isinstance(content_data, TextBlockContent):
                    parts.append(google_genai_types.Part.from_text(text=content_data.text))

                elif isinstance(content_data, ToolUseResponseContent):
                    while len(tool_requests_order) > 0:
                        if tool_requests_order[0] == content_data.tool_use_id:
                            function_call = google_genai_types.Part.from_function_call(
                                name=tool_requests[content_data.tool_use_id].tool_name,
                                args=tool_requests[content_data.tool_use_id].tool_input,
                            )
                            conversation_turns.append(
                                google_genai_types.Content(
                                    role=ConversationRoleGemini.MODEL.value, parts=[function_call]
                                )
                            )
                            tool_response = google_genai_types.Part.from_function_response(
                                name=content_data.tool_name, response=content_data.response
                            )
                            parts.append(tool_response)
                            tool_requests_order.pop(0)
                            break
                        tool_requests_order.pop(0)
                elif isinstance(content_data, ToolUseRequestContent):
                    tool_requests[content_data.tool_use_id] = content_data
                    tool_requests_order.append(content_data.tool_use_id)

                elif isinstance(content_data, ExtendedThinkingContent):
                    continue

                else:
                    attachment_id = content_data.attachment_id
                    if attachment_id not in attachment_data_task_map:
                        continue
                    attachment_data = await attachment_data_task_map[attachment_id]
                    if attachment_data.attachment_metadata.file_type.startswith("image/"):
                        parts.append(
                            google_genai_types.Part.from_bytes(
                                data=attachment_data.object_bytes,
                                mime_type=attachment_data.attachment_metadata.file_type,
                            )
                        )
            if parts:
                conversation_turns.append(google_genai_types.Content(role=role, parts=parts))

        return conversation_turns

    def _get_google_content_from_user_conversation_turn(
        self, conversation_turn: UserConversationTurn
    ) -> google_genai_types.Content:
        parts: List[google_genai_types.Part] = []
        for turn_content in conversation_turn.content:
            if isinstance(turn_content, UnifiedTextConversationTurnContent):
                parts.append(google_genai_types.Part.from_text(text=turn_content.text))

            if isinstance(turn_content, UnifiedImageConversationTurnContent):
                parts.append(
                    google_genai_types.Part.from_bytes(
                        data=turn_content.bytes_data,
                        mime_type=turn_content.image_mimetype,
                    )
                )
        return google_genai_types.Content(role=ConversationRoleGemini.USER.value, parts=parts)

    def _get_google_content_from_assistant_conversation_turn(
        self, conversation_turn: AssistantConversationTurn
    ) -> google_genai_types.Content:
        parts: List[google_genai_types.Part] = []
        for turn_content in conversation_turn.content:
            if isinstance(turn_content, UnifiedTextConversationTurnContent):
                parts.append(google_genai_types.Part.from_text(text=turn_content.text))

            if isinstance(turn_content, UnifiedToolRequestConversationTurnContent):
                parts.append(
                    google_genai_types.Part.from_function_call(
                        name=turn_content.tool_name,
                        args=turn_content.tool_input,
                    )
                )
        return google_genai_types.Content(role=ConversationRoleGemini.MODEL.value, parts=parts)

    def _get_google_content_from_tool_conversation_turn(
        self, conversation_turn: ToolConversationTurn
    ) -> google_genai_types.Content:
        return google_genai_types.Content(
            role=ConversationRoleGemini.USER.value,
            parts=[
                google_genai_types.Part.from_function_response(
                    name=turn_content.tool_name, response=turn_content.tool_use_response
                )
                for turn_content in conversation_turn.content
            ],
        )

    async def _get_google_content_from_conversation_turns(
        self, conversation_turns: List[UnifiedConversationTurn]
    ) -> List[google_genai_types.Content]:
        contents_arr: List[google_genai_types.Content] = []

        for turn in conversation_turns:
            if isinstance(turn, UserConversationTurn):
                contents_arr.append(self._get_google_content_from_user_conversation_turn(conversation_turn=turn))
            elif isinstance(turn, AssistantConversationTurn):
                contents_arr.append(self._get_google_content_from_assistant_conversation_turn(conversation_turn=turn))
            else:
                contents_arr.append(self._get_google_content_from_tool_conversation_turn(conversation_turn=turn))

        return contents_arr

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
        cache_config: PromptCacheConfig = PromptCacheConfig(  # Gemini caching is generally automatic
            tools=True, system_message=True, conversation=True
        ),
        search_web: bool = False,
        disable_caching: bool = False,
        conversation_turns: List[UnifiedConversationTurn] = [],
    ) -> Dict[str, Any]:
        """
        Formats the conversation for Vertex AI's Gemini model.

        Args:
            llm_model: The specific model requested (e.g., LLModels.GEMINI_2_5_PRO).
            prompt: Contains the initial system and user messages.
            tool_use_response: The result from a previous tool execution.
            previous_responses: History of the conversation.
            tools: Available tools for the model.
            tool_choice: How to handle tool selection (none, auto, required).
            cache_config: Caching configuration (mostly informational for Gemini).
            search_web: Add a tool to search web

        Returns:
            Dict[str, Any]: Payload containing 'contents', 'tools', 'system_instruction', 'tool_config'.
        """

        if tools and search_web:
            raise Exception("Functional tools and Web search tool can not be used together")
        model_config = self._get_model_config(llm_model)
        system_instruction: Optional[google_genai_types.Part] = None
        tool_config: Optional[google_genai_types.ToolConfig] = None

        # 1. Handle System Prompt
        if prompt and prompt.system_message:
            system_instruction = google_genai_types.Part.from_text(text=prompt.system_message)

        # 2. Process Conversation History (previous_responses)
        contents: List[google_genai_types.Content] = []

        if previous_responses and not conversation_turns:
            contents = await self.get_conversation_turns(previous_responses, attachment_data_task_map)
        elif conversation_turns:
            contents = await self._get_google_content_from_conversation_turns(conversation_turns=conversation_turns)

        # 3. Handle Current User Prompt
        user_parts: List[google_genai_types.Part] = []

        if prompt and prompt.user_message and not conversation_turns:
            user_parts.append(google_genai_types.Part.from_text(text=prompt.user_message))

        if attachments and not conversation_turns:
            for attachment in attachments:
                if attachment.attachment_id not in attachment_data_task_map:
                    continue
                attachment_data = await attachment_data_task_map[attachment.attachment_id]
                if attachment_data:
                    user_parts.append(
                        google_genai_types.Part.from_bytes(
                            data=attachment_data.object_bytes, mime_type=attachment_data.attachment_metadata.file_type
                        )
                    )

        if user_parts and not conversation_turns:
            contents.append(google_genai_types.Content(role=ConversationRoleGemini.USER.value, parts=user_parts))

        # 4. Handle Tool Use Response (if provided for this specific call)
        if tool_use_response and not conversation_turns:
            contents.append(
                google_genai_types.Content(
                    parts=[
                        google_genai_types.Part.from_function_response(
                            name=tool_use_response.content.tool_name, response=tool_use_response.content.response
                        )
                    ],
                    role=ConversationRoleGemini.USER.value,
                )
            )
        # 5. Handle Tools Definition
        tools = sorted(tools, key=lambda x: x.name) if tools else []
        formatted_tools = []
        for tool in tools:
            formatted_tool = google_genai_types.Tool(
                function_declarations=[
                    google_genai_types.FunctionDeclaration(
                        description=tool.description,
                        name=tool.name,
                        parameters=google_genai_types.Schema(**tool.input_schema.model_dump(mode="json")),
                    )
                ]
            )
            formatted_tools.append(formatted_tool)
        if search_web:
            formatted_tools = [google_genai_types.Tool(google_search=google_genai_types.GoogleSearch())]
        # Basic safety settings (optional, configure as needed)
        safety_settings = {}
        return {
            "max_tokens": model_config["MAX_TOKENS"],
            "contents": contents,
            "tools": formatted_tools,
            "tool_config": tool_config,
            "system_instruction": system_instruction,
            "safety_settings": safety_settings,
        }

    def _parse_non_streaming_response(
        self, response: google_genai_types.GenerateContentResponse
    ) -> NonStreamingResponse:
        """
        Parses the non-streaming response from Vertex AI's Gemini model.

        Args:
            response: The raw GenerateContentResponse from the Vertex AI API.

        Returns:
            NonStreamingResponse: Parsed response in your application's format.
        """
        content_blocks: List[ResponseData] = []
        input_tokens = 0
        output_tokens = 0
        cache_read_tokens = 0

        # Extract usage data
        if response.usage_metadata:
            output_tokens = response.usage_metadata.candidates_token_count  # Sum across candidates if multiple
            cache_read_tokens = response.usage_metadata.cached_content_token_count or 0
            input_tokens = (response.usage_metadata.prompt_token_count or 0) - cache_read_tokens

        # Check for safety blocks or empty candidates
        if not response.candidates:
            # Handle cases where the response was blocked or no content generated
            # You might want to check response.prompt_feedback for block reasons
            AppLogger.log_info(f"Warning: No candidates found in response. Feedback: {response.prompt_feedback}")
            # Return an empty or error response structure
            return NonStreamingResponse(content=[], usage=LLMUsage(input=input_tokens, output=output_tokens))

        # Process the first candidate (usually the only one unless configured otherwise)
        candidate = response.candidates[0]

        # Check finish reason (e.g., STOP, MAX_TOKENS, SAFETY, RECITATION, TOOL_CALL)
        _finish_reason = candidate.finish_reason.name
        # You might log or handle different finish reasons specifically

        # Check for safety ratings
        if candidate.safety_ratings:
            for rating in candidate.safety_ratings:
                if rating.blocked:
                    AppLogger.log_info(
                        f"Warning: Response content blocked due to safety rating: {rating.category.name if rating.category else 'UNKNOWN'}"
                    )
                    # Decide how to handle blocked content (e.g., return empty, raise error)

        # Extract content parts (text, function calls)
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if part.text:
                    content_blocks.append(TextBlockData(content=TextBlockContent(text=part.text)))
                elif part.function_call:
                    content_blocks.append(
                        ToolUseRequestData(
                            type=ContentBlockCategory.TOOL_USE_REQUEST,
                            content=ToolUseRequestContent(
                                tool_input=part.function_call.args,
                                tool_name=part.function_call.name,
                                tool_use_id=str(uuid.uuid4()),
                            ),
                        )
                    )

        return NonStreamingResponse(
            content=content_blocks,
            usage=LLMUsage(input=input_tokens or 0, output=output_tokens or 0, cache_read=cache_read_tokens),
        )

    async def _parse_streaming_response(  # noqa: C901
        self,
        response: AsyncIterator[google_genai_types.GenerateContentResponse],
        stream_id: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> StreamingResponse:
        stream_id = stream_id or str(uuid.uuid4())
        usage = LLMUsage(input=0, output=0, cache_read=0, cache_write=None)
        streaming_completed = asyncio.Event()

        # Manual token counting for when final usage is not available

        accumulated_events = []

        async def stream_content() -> AsyncIterator[StreamingEvent]:
            nonlocal usage
            nonlocal streaming_completed
            nonlocal accumulated_events
            nonlocal session_id

            self._active_streams[stream_id] = response
            current_running_block_type: Optional[ContentBlockCategory] = None
            try:
                async for chunk in response:
                    if self.checker:
                        await self.checker.enforce_cancellation_with_cleanup()

                    try:
                        event_blocks, event_block_category, event_usage = await self._get_parsed_stream_event(
                            chunk, current_running_block_type
                        )
                        if event_usage:
                            usage += event_usage
                        if event_blocks:
                            current_running_block_type = event_block_category
                            for event_block in event_blocks:
                                # Manual token counting for streaming content
                                accumulated_events.append(event_block)
                                yield event_block
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as e:  # noqa: BLE001
                AppLogger.log_error(f"Streaming Error in Google: {e}")
            finally:
                if self.checker:
                    await self.checker.stop_monitoring()
                streaming_completed.set()
                await close_client()

        async def get_usage() -> LLMUsage:
            nonlocal usage
            nonlocal streaming_completed
            await streaming_completed.wait()
            return usage

        async def get_accumulated_events() -> List[StreamingEvent]:
            nonlocal accumulated_events
            nonlocal streaming_completed
            await streaming_completed.wait()
            return accumulated_events

        async def close_client() -> None:
            try:
                if stream_id in self._active_streams and streaming_completed:
                    stream_iter = self._active_streams[stream_id]
                    await stream_iter.aclose()
                    del self._active_streams[stream_id]
            except Exception as e:  # noqa: BLE001
                AppLogger.log_error(f"Error closing Google LLM client for stream {stream_id}: {e}")
            if stream_id in self._active_streams:
                del self._active_streams[stream_id]

        return StreamingResponse(
            content=stream_content(),
            usage=asyncio.create_task(get_usage()),
            type=LLMCallResponseTypes.STREAMING,
            accumulated_events=asyncio.create_task(get_accumulated_events()),
        )

    async def _get_parsed_stream_event(  # noqa: C901
        self,
        chunk: google_genai_types.GenerateContentResponse,
        current_running_block_type: Optional[ContentBlockCategory] = None,
    ) -> Tuple[List[Optional[StreamingEvent]], Optional[ContentBlockCategory], Optional[LLMUsage]]:
        event_blocks: List[StreamingEvent] = []
        usage: LLMUsage = LLMUsage(input=0, output=0, cache_read=0, cache_write=None)
        candidate = chunk.candidates[0]
        # Process all parts instead of just the first one
        parts = candidate.content.parts if candidate.content and candidate.content.parts else []

        # Handle malformed function call first
        if candidate.finish_reason == "MALFORMED_FUNCTION_CALL":
            AppLogger.log_warn("Malformed function call detected in model response.")

            event_blocks.append(
                MalformedToolUseRequest(
                    content=MalformedToolUseRequestContent(
                        reason="Model returned a malformed function call",
                        raw_payload=candidate.finish_message or "No message provided",
                    )
                )
            )

            # Still extract token usage if available
            if chunk.usage_metadata:
                usage.input = (chunk.usage_metadata.prompt_token_count or 0) - (
                    chunk.usage_metadata.cached_content_token_count or 0
                )
                usage.output = chunk.usage_metadata.candidates_token_count or 0
                usage.cache_read = chunk.usage_metadata.cached_content_token_count or 0
            return event_blocks, None, usage

        for i, part in enumerate(parts):
            # Block type is changing, so mark current running block end and start new block.
            if part.text and current_running_block_type != ContentBlockCategory.TEXT_BLOCK:
                if current_running_block_type == ContentBlockCategory.TOOL_USE_REQUEST:
                    event_block = ToolUseRequestEnd()
                    event_blocks.append(event_block)
                event_block = TextBlockStart()
                event_blocks.append(event_block)
                current_running_block_type = ContentBlockCategory.TEXT_BLOCK
            elif part.function_call:
                # End previous block if needed
                if current_running_block_type == ContentBlockCategory.TEXT_BLOCK:
                    event_block = TextBlockEnd()
                    event_blocks.append(event_block)
                elif current_running_block_type == ContentBlockCategory.TOOL_USE_REQUEST:
                    # End previous tool use request before starting a new one
                    event_block = ToolUseRequestEnd()
                    event_blocks.append(event_block)

                # Start new tool use request for each function call
                function_call: google_genai_types.FunctionCall = part.function_call
                event_block = ToolUseRequestStart(
                    content=ToolUseRequestStartContent(
                        tool_name=function_call.name, tool_use_id=function_call.id or str(uuid.uuid4())
                    )
                )
                event_blocks.append(event_block)

                # Google provides complete function call args
                args_json = "{}"
                if part.function_call.args:
                    if isinstance(part.function_call.args, str):
                        # Validate if the string is already valid JSON
                        try:
                            json.loads(part.function_call.args)
                            args_json = part.function_call.args
                        except (json.JSONDecodeError, ValueError, TypeError) as e:
                            # If not valid JSON, treat it as a plain string and wrap it properly
                            AppLogger.log_warn(f"Invalid JSON in function call args, wrapping as string: {e}")
                            try:
                                args_json = json.dumps({"value": part.function_call.args})
                            except (TypeError, ValueError) as wrap_error:
                                AppLogger.log_error(f"Failed to wrap function call args as JSON: {wrap_error}")
                                args_json = json.dumps({"error": "Invalid function arguments"})
                    else:
                        # Convert dict/object to JSON string
                        try:
                            args_json = json.dumps(part.function_call.args)
                        except (TypeError, ValueError) as e:
                            AppLogger.log_error(f"Error serializing function call args: {e}")
                            args_json = json.dumps({"error": "Failed to serialize function arguments"})

                event_block = ToolUseRequestDelta(content=ToolUseRequestDeltaContent(input_params_json_delta=args_json))
                event_blocks.append(event_block)

                # End this tool use request immediately
                event_block = ToolUseRequestEnd()
                event_blocks.append(event_block)
                current_running_block_type = None

            # ============================ Add data of current block ======================= #
            if part.text:
                event_block = TextBlockDelta(content=TextBlockDeltaContent(text=part.text))
                event_blocks.append(event_block)
                current_running_block_type = ContentBlockCategory.TEXT_BLOCK

        # Handle finish reason at the end
        if candidate.finish_reason:
            if chunk.usage_metadata:
                usage.input = (chunk.usage_metadata.prompt_token_count or 0) - (
                    chunk.usage_metadata.cached_content_token_count or 0
                )
                usage.output = chunk.usage_metadata.candidates_token_count or 0
                usage.cache_read = chunk.usage_metadata.cached_content_token_count or 0

            if current_running_block_type == ContentBlockCategory.TEXT_BLOCK:
                event_block = TextBlockEnd()
                event_blocks.append(event_block)
            # Don't append None when current_running_block_type is not TEXT_BLOCK

        return event_blocks, current_running_block_type, usage

    async def call_service_client(
        self,
        session_id: int,
        llm_payload: Dict[str, Any],
        model: LLModels,
        stream: bool = False,
        response_type: Optional[str] = None,
        parallel_tool_calls: bool = True,
        text_format: Optional[Type[BaseModel]] = None,
        reasoning: Optional[Reasoning] = None,
    ) -> UnparsedLLMCallResponse:
        """
        Calls the Vertex AI service client.

        Args:
            llm_payload: The structured payload from build_llm_payload.
            model: The LLModels enum value specifying which model to use.
            stream: Whether to use streaming mode.
            response_type: Optional response format hint (less common for Gemini chat).
            response_schema: Optional: response structure

        Returns:
            Either a NonStreamingResponse or an AsyncIterator for streaming.
        """
        model_config = self._get_model_config(model)  # Get your internal config
        vertex_model_name = model_config.get("NAME")
        max_output_tokens = model_config.get("MAX_TOKENS") or 16384
        thinking_budget_tokens = model_config.get("THINKING_BUDGET_TOKENS", 4096)
        temperature = model_config.get("TEMPERATURE", 0.5)
        stream_id = str(uuid.uuid4())

        if stream:
            response = await self.client.get_llm_stream_response(
                model_name=vertex_model_name,
                contents=llm_payload["contents"],
                tools=llm_payload.get("tools"),
                tool_config=llm_payload.get("tool_config"),
                system_instruction=llm_payload.get("system_instruction"),
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                thinking_budget_tokens=thinking_budget_tokens,
            )
            return await self._parse_streaming_response(response, stream_id, session_id)
        else:
            response = await self.client.get_llm_non_stream_response(
                model_name=vertex_model_name,
                contents=llm_payload["contents"],
                tools=llm_payload.get("tools"),
                tool_config=llm_payload.get("tool_config"),
                system_instruction=llm_payload.get("system_instruction"),
                max_output_tokens=max_output_tokens,
            )
            return self._parse_non_streaming_response(response)

    async def get_tokens(
        self,
        content: str,
        model: LLModels,
    ) -> int:
        model_config = self._get_model_config(model)  # Get your internal config
        vertex_model_name = model_config["NAME"]
        tokens = await self.client.get_tokens(content, vertex_model_name)
        return tokens

    def _extract_payload_content_for_token_counting(self, llm_payload: Dict[str, Any]) -> str:  # noqa : C901
        """
        Extract the relevant content from LLM payload that will be sent to the LLM for token counting.
        This handles Google's payload structure.
        """
        content_parts = []

        try:
            # Google structure: system_instruction + contents array
            if "system_instruction" in llm_payload and llm_payload["system_instruction"]:
                # system_instruction is a Part object, extract text
                if hasattr(llm_payload["system_instruction"], "text"):
                    content_parts.append(llm_payload["system_instruction"].text)

            if "contents" in llm_payload:
                for content in llm_payload["contents"]:
                    if hasattr(content, "parts"):
                        for part in content.parts:
                            if hasattr(part, "text") and part.text:
                                content_parts.append(part.text)
                            elif hasattr(part, "function_response"):
                                content_parts.append(str(part.function_response))

            # Include tools information for token counting if present
            if "tools" in llm_payload and llm_payload["tools"]:
                try:
                    # Handle Google's Tool objects which are not JSON serializable
                    tools_text_parts = []
                    for tool in llm_payload["tools"]:
                        if hasattr(tool, "function_declarations"):
                            for func_decl in tool.function_declarations:
                                if hasattr(func_decl, "name"):
                                    tools_text_parts.append(func_decl.name)
                                if hasattr(func_decl, "description"):
                                    tools_text_parts.append(func_decl.description)
                    if tools_text_parts:
                        content_parts.append(" ".join(tools_text_parts))
                except Exception as e:  # noqa : BLE001
                    AppLogger.log_warn(f"Error processing tools for token counting: {e}")
                    # Skip tools if they can't be processed
                    pass

        except Exception as e:  # noqa : BLE001
            AppLogger.log_warn(f"Error extracting payload content for token counting: {e}")
            # Fallback: return a simple placeholder instead of trying to serialize non-serializable objects
            return "Unable to extract content for token counting"

        return "\n".join(content_parts)
