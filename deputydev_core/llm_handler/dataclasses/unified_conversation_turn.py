from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class UnifiedConversationRole(Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


class UnifiedConversationTurnContentType(Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    TOOL_REQUEST = "TOOL_REQUEST"
    TOOL_RESPONSE = "TOOL_RESPONSE"


class UnifiedTextConversationTurnContent(BaseModel):
    type: Literal[UnifiedConversationTurnContentType.TEXT] = UnifiedConversationTurnContentType.TEXT
    text: str


class UnifiedToolRequestConversationTurnContent(BaseModel):
    type: Literal[UnifiedConversationTurnContentType.TOOL_REQUEST] = UnifiedConversationTurnContentType.TOOL_REQUEST
    tool_use_id: str
    tool_name: str
    tool_input: Dict[str, Any]


class UnifiedToolResponseConversationTurnContent(BaseModel):
    type: Literal[UnifiedConversationTurnContentType.TOOL_RESPONSE] = UnifiedConversationTurnContentType.TOOL_RESPONSE
    tool_use_response: Dict[str, Any]
    tool_name: str
    tool_use_id: str


class UnifiedImageConversationTurnContent(BaseModel):
    type: Literal[UnifiedConversationTurnContentType.IMAGE] = UnifiedConversationTurnContentType.IMAGE
    bytes_data: bytes
    image_mimetype: str


UnifiedUserConversationTurnContent = Annotated[
    Union[
        UnifiedTextConversationTurnContent,
        UnifiedImageConversationTurnContent,
    ],
    Field(discriminator="type"),
]


UnifiedAssistantConversationTurnContent = Annotated[
    Union[
        UnifiedTextConversationTurnContent,
        UnifiedToolRequestConversationTurnContent,
    ],
    Field(discriminator="type"),
]


class ToolConversationTurn(BaseModel):
    role: Literal[UnifiedConversationRole.TOOL] = UnifiedConversationRole.TOOL
    content: List[UnifiedToolResponseConversationTurnContent]
    cache_breakpoint: Optional[bool] = None


class UserConversationTurn(BaseModel):
    role: Literal[UnifiedConversationRole.USER] = UnifiedConversationRole.USER
    content: List[UnifiedUserConversationTurnContent]
    cache_breakpoint: Optional[bool] = None


class AssistantConversationTurn(BaseModel):
    role: Literal[UnifiedConversationRole.ASSISTANT] = UnifiedConversationRole.ASSISTANT
    content: List[UnifiedAssistantConversationTurnContent]
    cache_breakpoint: Optional[bool] = None


UnifiedConversationTurn = Annotated[
    Union[
        ToolConversationTurn,
        UserConversationTurn,
        AssistantConversationTurn,
    ],
    Field(discriminator="role"),
]
