from enum import Enum
from typing import List, Optional, Dict, Any, Union
import mcp
from deputydev_core.services.mcp.contants import (
    DEFAULT_MCP_READ_TIMEOUT_SECONDS,
    MIN_CONNECTION_TIMEOUT_SECONDS,
    DEFAULT_CONNECTION_TIMEOUT_SECONDS,
    MAX_ALLOWED_TOOLS,
    MAX_CHARACTERS_TO_RETURN,
    DEFAULT_AUTO_APPROVE,
)
from pydantic import BaseModel, Field, validator, HttpUrl, field_validator
from fastmcp.client.transports import (
    StdioTransport,
    SSETransport,
    StreamableHttpTransport,
)


class BaseConfigModel(BaseModel):
    auto_approve_tools: Optional[
        List[str]
    ] = []  # list of tools supported for auto approve
    disabled: Optional[bool] = False  # handles servers disable state
    connection_timeout: Optional[int] = None
    read_timeout: Optional[int] = None
    auto_approve: Optional[bool] = False

    @field_validator("read_timeout")
    @classmethod
    def validate_timeout(cls, v):
        if v and v < MIN_CONNECTION_TIMEOUT_SECONDS:
            raise ValueError(
                f"Timeout must be at least {MIN_CONNECTION_TIMEOUT_SECONDS} seconds"
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


class McpTool(BaseModel):
    name: str
    description: str
    return_type: str
    schema: Dict[str, Any]
    auto_approve: Optional[bool] = True


class McpToolCallResponse(BaseModel):
    result: Any


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
    status: ConnectionStatus
    disabled: bool
    error: Optional[str]
    tools: Optional[List[mcp.types.Tool]]
    resources: Optional[List[McpResource]]
    resource_templates: Optional[List[McpResourceTemplate]]
    auto_approve: bool
    read_timeout: int


class DefaultSettings(BaseModel):
    max_tools: Optional[int] = MAX_ALLOWED_TOOLS
    connection_timeout: Optional[int] = DEFAULT_CONNECTION_TIMEOUT_SECONDS
    read_timeout: Optional[int] = DEFAULT_MCP_READ_TIMEOUT_SECONDS
    buffer_size: Optional[int] = MAX_CHARACTERS_TO_RETURN
    auto_approve: Optional[bool] = DEFAULT_AUTO_APPROVE


class McpSettingsModel(BaseModel):
    mcp_servers: Dict[str, ServerConfigModel] = Field(default_factory=dict)
    default_settings: Optional[DefaultSettings] = DefaultSettings()


class ServersDetails(BaseModel):
    name: str
    status: str
    tool_count: int
    tools: Optional[List[mcp.types.Tool]]
    error: Optional[str]
    disabled: bool
    auto_approve: bool


class ServerFilters(BaseModel):
    connection_status: List[ConnectionStatus] = ConnectionStatus.connected


class Tools(BaseModel):
    server_name: str
    tools: Optional[List[mcp.types.Tool]]


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
