import asyncio
from asyncio import Task
from enum import Enum
from typing import Annotated, Any, AsyncIterator, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from deputydev_core.llm_handler.models.dto.message_thread_dto import (
    LLModels,
    LLMUsage,
    ResponseData,
)


class LLMCallResponseTypes(Enum):
    NON_STREAMING = "NON_STREAMING"
    STREAMING = "STREAMING"


class LLMMeta(BaseModel):
    llm_model: LLModels
    prompt_type: str
    token_usage: LLMUsage


class UserAndSystemMessages(BaseModel):
    user_message: str
    system_message: Optional[str] = None
    cached_message: Optional[str] = None


class ConversationRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationRoleGemini(Enum):
    USER = "user"
    MODEL = "model"


class ConversationTurn(BaseModel):
    role: ConversationRole
    content: Union[str, List[Dict[str, Any]]]


class JSONSchemaType(Enum):
    NULL = "null"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NUMBER = "number"
    INTEGER = "integer"
    STRING = "string"


class JSONSchema(BaseModel):
    type: Optional[Union[str, list[str]]] = Field(default=None, alias="type")
    format: Optional[str] = Field(default=None, alias="format")
    title: Optional[str] = Field(default=None, alias="title")
    description: Optional[str] = Field(default=None, alias="description")
    default: Optional[Any] = Field(default=None, alias="default")

    items: Optional["JSONSchema"] = Field(default=None, alias="items")
    min_items: Optional[int] = Field(default=None, alias="minItems")
    max_items: Optional[int] = Field(default=None, alias="maxItems")
    enum: Optional[list[Any]] = Field(default=None, alias="enum")

    properties: Optional[dict[str, "JSONSchema"]] = Field(default=None, alias="properties")
    required: Optional[list[str]] = Field(default=None, alias="required")
    min_properties: Optional[int] = Field(default=None, alias="minProperties")
    max_properties: Optional[int] = Field(default=None, alias="maxProperties")

    minimum: Optional[float] = Field(default=None, alias="minimum")
    maximum: Optional[float] = Field(default=None, alias="maximum")
    min_length: Optional[int] = Field(default=None, alias="minLength")
    max_length: Optional[int] = Field(default=None, alias="maxLength")
    pattern: Optional[str] = Field(default=None, alias="pattern")

    any_of: Optional[list["JSONSchema"]] = Field(default=None, alias="anyOf")

    class Config:
        populate_by_name = True  # Allows snake_case or camelCase during input


class ConversationTool(BaseModel):
    name: str
    description: str
    input_schema: JSONSchema


class PromptCacheConfig(BaseModel):
    conversation: bool
    tools: bool
    system_message: bool


# ALL CONTENT BLOCK TYPES
class StreamingEventType(Enum):
    TEXT_BLOCK_START = "TEXT_START"
    TEXT_BLOCK_DELTA = "TEXT_DELTA"
    TEXT_BLOCK_END = "TEXT_BLOCK_END"
    TOOL_USE_REQUEST_START = "TOOL_USE_REQUEST_START"
    TOOL_USE_REQUEST_DELTA = "TOOL_USE_REQUEST_DELTA"
    TOOL_USE_REQUEST_END = "TOOL_USE_REQUEST_END"
    THINKING_BLOCK_START = "THINKING_BLOCK_START"
    THINKING_BLOCK_DELTA = "THINKING_BLOCK_DELTA"
    THINKING_BLOCK_END = "THINKING_BLOCK_END"
    CODE_BLOCK_START = "CODE_BLOCK_START"
    CODE_BLOCK_DELTA = "CODE_BLOCK_DELTA"
    CODE_BLOCK_END = "CODE_BLOCK_END"
    REDACTED_THINKING = "REDACTED_THINKING"
    EXTENDED_THINKING_BLOCK_START = "EXTENDED_THINKING_BLOCK_START"
    EXTENDED_THINKING_BLOCK_END = "EXTENDED_THINKING_BLOCK_END"
    EXTENDED_THINKING_BLOCK_DELTA = "EXTENDED_THINKING_BLOCK_DELTA"
    MALFORMED_TOOL_USE_REQUEST = "MALFORMED_TOOL_USE_REQUEST"


class Reasoning(Enum):
    NONE = "NONE"
    MINIMAL = "MINIMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# TOOL_USE_REQUEST BLOCK CONTENTS
class ToolUseRequestStartContent(BaseModel):
    tool_name: str
    tool_use_id: str


class ToolUseRequestDeltaContent(BaseModel):
    input_params_json_delta: str


# TEXT_BLOCK CONTENTS
class TextBlockDeltaContent(BaseModel):
    text: str


# STREAMING CONTENT BLOCKS


# TEXT BLOCKS
class TextBlockStart(BaseModel):
    type: Literal[StreamingEventType.TEXT_BLOCK_START] = StreamingEventType.TEXT_BLOCK_START


class TextBlockDelta(BaseModel):
    type: Literal[StreamingEventType.TEXT_BLOCK_DELTA] = StreamingEventType.TEXT_BLOCK_DELTA
    content: TextBlockDeltaContent

    def __add__(self, other: "TextBlockDelta") -> "TextBlockDelta":
        return TextBlockDelta(content=TextBlockDeltaContent(text=self.content.text + other.content.text))


class TextBlockEnd(BaseModel):
    type: Literal[StreamingEventType.TEXT_BLOCK_END] = StreamingEventType.TEXT_BLOCK_END


# TOOL USE REQUEST BLOCKS
class ToolUseRequestStart(BaseModel):
    type: Literal[StreamingEventType.TOOL_USE_REQUEST_START] = StreamingEventType.TOOL_USE_REQUEST_START
    content: ToolUseRequestStartContent


class ToolUseRequestDelta(BaseModel):
    type: Literal[StreamingEventType.TOOL_USE_REQUEST_DELTA] = StreamingEventType.TOOL_USE_REQUEST_DELTA
    content: ToolUseRequestDeltaContent

    def __add__(self, other: "ToolUseRequestDelta") -> "ToolUseRequestDelta":
        return ToolUseRequestDelta(
            content=ToolUseRequestDeltaContent(
                input_params_json_delta=self.content.input_params_json_delta + other.content.input_params_json_delta
            )
        )


class ToolUseRequestEnd(BaseModel):
    type: Literal[StreamingEventType.TOOL_USE_REQUEST_END] = StreamingEventType.TOOL_USE_REQUEST_END


class MalformedToolUseRequestContent(BaseModel):
    reason: Optional[str] = None
    raw_payload: Optional[str] = None


class MalformedToolUseRequest(BaseModel):
    type: Literal[StreamingEventType.MALFORMED_TOOL_USE_REQUEST] = StreamingEventType.MALFORMED_TOOL_USE_REQUEST
    content: MalformedToolUseRequestContent


class ExtendedThinkingBlockStart(BaseModel):
    type: Literal[StreamingEventType.EXTENDED_THINKING_BLOCK_START] = StreamingEventType.EXTENDED_THINKING_BLOCK_START


class RedactedThinking(BaseModel):
    type: Literal[StreamingEventType.REDACTED_THINKING] = StreamingEventType.REDACTED_THINKING
    data: str


class ExtendedThinkingBlockDeltaContent(BaseModel):
    thinking_delta: str


class ExtendedThinkingBlockEndContent(BaseModel):
    signature: str


class ExtendedThinkingBlockDelta(BaseModel):
    type: Literal[StreamingEventType.EXTENDED_THINKING_BLOCK_DELTA] = StreamingEventType.EXTENDED_THINKING_BLOCK_DELTA
    content: ExtendedThinkingBlockDeltaContent

    def __add__(self, other: "ExtendedThinkingBlockDelta") -> "ExtendedThinkingBlockDelta":
        return ExtendedThinkingBlockDelta(
            content=ExtendedThinkingBlockDeltaContent(
                thinking_delta=self.content.thinking_delta + other.content.thinking_delta
            )
        )


class ExtendedThinkingBlockEnd(BaseModel):
    type: Literal[StreamingEventType.EXTENDED_THINKING_BLOCK_END] = StreamingEventType.EXTENDED_THINKING_BLOCK_END
    content: ExtendedThinkingBlockEndContent


TextBlockEvents = Annotated[Union[TextBlockStart, TextBlockDelta, TextBlockEnd], Field(discriminator="type")]
ToolUseRequestEvents = Annotated[
    Union[ToolUseRequestStart, ToolUseRequestDelta, ToolUseRequestEnd, MalformedToolUseRequest],
    Field(discriminator="type"),
]
ExtendedThinkingEvents = Annotated[
    Union[ExtendedThinkingBlockStart, ExtendedThinkingBlockDelta, ExtendedThinkingBlockEnd], Field(discriminator="type")
]
RedactedThinkingEvent = Annotated[RedactedThinking, Field(discriminator="type")]


StreamingEvent = Annotated[
    Union[
        TextBlockEvents,
        ToolUseRequestEvents,
        ExtendedThinkingEvents,
        RedactedThinkingEvent,
    ],
    Field(discriminator="type"),
]


class StreamingResponse(BaseModel):
    type: Literal[LLMCallResponseTypes.STREAMING] = LLMCallResponseTypes.STREAMING
    content: AsyncIterator[StreamingEvent]
    usage: Task[LLMUsage]
    cost: Optional[Task[Optional[float]]] = None
    accumulated_events: Task[List[StreamingEvent]]

    model_config = ConfigDict(arbitrary_types_allowed=True)


class NonStreamingResponse(BaseModel):
    type: Literal[LLMCallResponseTypes.NON_STREAMING] = LLMCallResponseTypes.NON_STREAMING
    content: List[ResponseData]
    usage: LLMUsage
    cost: Optional[float] = None


UnparsedLLMCallResponse = Annotated[
    Union[StreamingResponse, NonStreamingResponse],
    Field(discriminator="type"),
]


class ParsedLLMCallResponseCommon(BaseModel):
    prompt_vars: Dict[str, Any]
    prompt_id: str
    model_used: LLModels


class StreamingParsedLLMCallResponse(ParsedLLMCallResponseCommon, StreamingResponse):
    parsed_content: AsyncIterator[Any]
    query_id: int
    llm_response_storage_task: asyncio.Task[NonStreamingResponse]


class NonStreamingParsedLLMCallResponse(ParsedLLMCallResponseCommon, NonStreamingResponse):
    parsed_content: Any
    query_id: int


ParsedLLMCallResponse = Annotated[
    Union[
        StreamingParsedLLMCallResponse,
        NonStreamingParsedLLMCallResponse,
    ],
    Field(discriminator="type"),
]


class LLMToolChoice(Enum):
    NONE = "NONE"
    AUTO = "AUTO"
    REQUIRED = "REQUIRED"
