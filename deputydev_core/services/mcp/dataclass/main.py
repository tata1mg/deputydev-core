from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl, field_validator
from fastmcp.client.transports import (
    StdioTransport,
    SSETransport,
    StreamableHttpTransport,
)
from mcp.types import Tool


class BaseConfigModel(BaseModel):
    auto_approve_tools: Optional[Union[List[str], str]] = None
    disabled: Optional[bool] = False  # handles servers disable state
    connection_timeout: Optional[int] = None
    read_timeout: Optional[int] = None

    @field_validator("read_timeout")
    @classmethod
    def validate_timeout(cls, v):
        if v and v < 1:
            raise ValueError(
                f"Timeout must be at least {1} seconds"
            )
        return v


class TransportTypes(Enum):
    stdio = "stdio"
    sse = "sse"
    streamable_http = "streamable-http"


class McpResourceTemplate(BaseModel):
    id: str
    name: str
    description: str
    schema: Dict[str, Any]


class McpToolCallResponse(BaseModel):
    result: Any


class ExtendedTool(Tool):
    auto_approve: bool


class McpResourceId(BaseModel):
    uri: str


class McpResource(BaseModel):
    id: McpResourceId
    name: str
    description: str
    format: str


class SseConfigModel(BaseConfigModel):
    url: str
    transport_type: str = TransportTypes.sse.value

    def dict(self, *args, **kwargs):
        result = super().dict(*args, **kwargs)
        result["url"] = str(result["url"])
        return result

    class Config:
        json_encoders = {HttpUrl: str}


class StreamableHTTP(BaseConfigModel):
    url: str
    transport_type: str = TransportTypes.streamable_http.value

    def dict(self, *args, **kwargs):
        result = super().dict(*args, **kwargs)
        result["url"] = str(result["url"])
        return result

    class Config:
        json_encoders = {HttpUrl: str}


class StdioConfigModel(BaseConfigModel):
    command: str
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    transport_type: str = TransportTypes.stdio.value

    class Config:
        use_enum_values = True


ServerConfigModel = Union[StdioConfigModel, SseConfigModel, StreamableHTTP]
Transports = Union[StdioTransport, SSETransport, StreamableHttpTransport]


class ConnectionStatus(Enum):
    connecting = "connecting"
    connected = "connected"
    disconnected = "disconnected"


class McpServer(BaseModel):
    name: str
    config: str
    disabled: bool
    read_timeout: int
    status: ConnectionStatus
    error: Optional[str]
    tools: Optional[List[ExtendedTool]]


class McpDefaultSettings(BaseModel):
    max_tools: Optional[int] = None
    connection_timeout: Optional[int] = None
    read_timeout: Optional[int] = None
    buffer_size: Optional[int] = None


class McpSettingsModel(BaseModel):
    mcp_servers: Dict[str, ServerConfigModel] = Field(default_factory=dict)
    default_settings: Optional[McpDefaultSettings] = None


class ServersDetails(BaseModel):
    name: str
    status: str
    tool_count: int
    tools: Optional[List[Tool]]
    error: Optional[str]
    disabled: bool


class ServerFilters(BaseModel):
    connection_status: List[ConnectionStatus] = ConnectionStatus.connected


class Tools(BaseModel):
    server_name: str
    tools: Optional[List[ExtendedTool]]


class McpResponseMeta(BaseModel):
    message: str


class McpResponse(BaseModel):
    data: Optional[Any] = None
    is_error: bool = False
    meta: Optional[McpResponseMeta] = None


class ToolInvokeRequest(BaseModel):
    server_name: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
