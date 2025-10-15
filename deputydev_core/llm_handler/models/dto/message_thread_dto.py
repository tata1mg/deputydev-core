from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field


class MessageThreadActor(Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class MessageType(Enum):
    QUERY = "QUERY"
    RESPONSE = "RESPONSE"
    TOOL_RESPONSE = "TOOL_RESPONSE"


class ContentBlockCategory(str, Enum):
    TEXT_BLOCK = "TEXT_BLOCK"
    TOOL_USE_REQUEST = "TOOL_USE_REQUEST"
    TOOL_USE_RESPONSE = "TOOL_USE_RESPONSE"
    EXTENDED_THINKING = "EXTENDED_THINKING"
    FILE = "FILE"


class TextBlockContent(BaseModel):
    text: str


class FileContent(BaseModel):
    attachment_id: int


class ToolUseRequestContent(BaseModel):
    tool_input: Dict[str, Any]
    tool_name: str
    tool_use_id: str


class ToolUseResponseContent(BaseModel):
    tool_name: str
    tool_use_id: str
    response: Union[str, Dict[str, Any]]


class ExtendedThinkingContent(BaseModel):
    type: Literal["thinking", "redacted_thinking"] = "thinking"
    thinking: str
    signature: Optional[str] = ""


class ExtendedThinkingData(BaseModel):
    type: Literal[ContentBlockCategory.EXTENDED_THINKING] = ContentBlockCategory.EXTENDED_THINKING
    content: ExtendedThinkingContent


class TextBlockData(BaseModel):
    type: Literal[ContentBlockCategory.TEXT_BLOCK] = ContentBlockCategory.TEXT_BLOCK
    content: TextBlockContent
    content_vars: Optional[Dict[str, Any]] = None


class FileBlockData(BaseModel):
    type: Literal[ContentBlockCategory.FILE] = ContentBlockCategory.FILE
    content: FileContent


class ToolUseRequestData(BaseModel):
    type: Literal[ContentBlockCategory.TOOL_USE_REQUEST] = ContentBlockCategory.TOOL_USE_REQUEST
    content: ToolUseRequestContent


class ToolUseResponseData(BaseModel):
    type: Literal[ContentBlockCategory.TOOL_USE_RESPONSE] = ContentBlockCategory.TOOL_USE_RESPONSE
    content: ToolUseResponseContent


ResponseData = Annotated[
    Union[ExtendedThinkingData, TextBlockData, FileBlockData, ToolUseRequestData], Field(discriminator="type")
]

MessageData = Annotated[Union[ResponseData, ToolUseResponseData], Field(discriminator="type")]


class LLModels(Enum):
    GPT_4O = "GPT_4O"
    CLAUDE_3_POINT_5_SONNET = "CLAUDE_3_POINT_5_SONNET"
    CLAUDE_3_POINT_7_SONNET = "CLAUDE_3_POINT_7_SONNET"
    CLAUDE_4_POINT_5_SONNET = "CLAUDE_4_POINT_5_SONNET"
    CLAUDE_4_POINT_5_HAIKU = "CLAUDE_4_POINT_5_HAIKU"
    CLAUDE_4_SONNET = "CLAUDE_4_SONNET"
    CLAUDE_4_SONNET_THINKING = "CLAUDE_4_SONNET_THINKING"
    GPT_40_MINI = "GPT_40_MINI"
    GPT_O1_MINI = "GPT_O1_MINI"
    GEMINI_2_POINT_5_PRO = "GEMINI_2_POINT_5_PRO"
    GEMINI_2_POINT_0_FLASH = "GEMINI_2_POINT_0_FLASH"
    GEMINI_2_POINT_5_FLASH = "GEMINI_2_POINT_5_FLASH"
    GEMINI_2_POINT_5_FLASH_LITE = "GEMINI_2_POINT_5_FLASH_LITE"
    GPT_4_POINT_1 = "GPT_4_POINT_1"
    GPT_4_POINT_1_MINI = "GPT_4_POINT_1_MINI"
    GPT_4_POINT_1_NANO = "GPT_4_POINT_1_NANO"
    GPT_O3_MINI = "GPT_O3_MINI"
    KIMI_K2 = "KIMI_K2"
    QWEN_3_CODER = "QWEN_3_CODER"
    OPENROUTER_GPT_5 = "OPENROUTER_GPT_5"
    OPENROUTER_GROK_CODE_FAST_1 = "OPENROUTER_GROK_CODE_FAST_1"
    OPENROUTER_GROK_4_FAST = "OPENROUTER_GROK_4_FAST"
    OPENROUTER_GPT_5_MINI = "OPENROUTER_GPT_5_MINI"
    OPENROUTER_GPT_5_NANO = "OPENROUTER_GPT_5_NANO"
    OPENROUTER_GPT_5_CODEX = "OPENROUTER_GPT_5_CODEX"
    OPENROUTER_GPT_4_POINT_1 = "OPENROUTER_GPT_4_POINT_1"


class LLMUsage(BaseModel):
    input: int
    output: int
    cache_read: Optional[int] = None
    cache_write: Optional[int] = None

    def __add__(self, other: "LLMUsage") -> "LLMUsage":
        return LLMUsage(
            input=self.input + other.input,
            output=self.output + other.output,
            cache_read=(
                (self.cache_read or 0) + (other.cache_read or 0)
                if self.cache_read is not None or other.cache_read is not None
                else None
            ),
            cache_write=(
                (self.cache_write or 0) + (other.cache_write or 0)
                if self.cache_write is not None or other.cache_write is not None
                else None
            ),
        )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MessageCallChainCategory(Enum):
    CLIENT_CHAIN = "CLIENT_CHAIN"
    SYSTEM_CHAIN = "SYSTEM_CHAIN"


class MessageThreadData(BaseModel):
    session_id: int
    actor: MessageThreadActor
    query_id: Optional[int] = None
    message_type: MessageType
    conversation_chain: List[int] = []
    data_hash: str
    message_data: Sequence[MessageData]
    prompt_type: str
    prompt_category: str
    llm_model: LLModels
    usage: Optional[LLMUsage] = None
    call_chain_category: MessageCallChainCategory
    metadata: Optional[Dict[str, Any]] = None
    cost: Optional[float] = None


class MessageThreadDTO(MessageThreadData):
    id: int
    created_at: datetime
    updated_at: datetime
