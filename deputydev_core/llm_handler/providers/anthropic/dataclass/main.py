from enum import Enum
from typing import Any, Dict, Literal, TypedDict, Union


class AnthropicResponseTypes(Enum):
    TEXT = "text"
    TOOL_USE = "tool_use"


class AnthropicContentTextResponse(TypedDict):
    type: Literal[AnthropicResponseTypes.TEXT]
    text: str


class AnthropicContentToolUseResponse(TypedDict):
    type: Literal[AnthropicResponseTypes.TOOL_USE]
    id: str
    name: str
    input: Dict[str, Any]


AnthropicNonStreamingContentResponse = Union[AnthropicContentTextResponse, AnthropicContentToolUseResponse]
