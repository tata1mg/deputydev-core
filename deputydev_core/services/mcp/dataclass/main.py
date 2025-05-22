from enum import Enum
from typing import List, Optional, Dict, Any, Union
import mcp
from deputydev_core.services.mcp.contants import (
    MIN_MCP_TIMEOUT_SECONDS,
    DEFAULT_MCP_TIMEOUT_SECONDS,
)
from pydantic import BaseModel, Field, validator, HttpUrl


class BaseConfigModel(BaseModel):
    auto_approve: Optional[List[str]] = [] # list of tools supported for auto approve
    disabled: Optional[bool] = False  # handles servers disable state
    timeout: int = DEFAULT_MCP_TIMEOUT_SECONDS # handles timeout for server

    @validator("timeout")
    def validate_timeout(cls, v):
        if v < MIN_MCP_TIMEOUT_SECONDS:
            raise ValueError(
                f"Timeout must be at least {MIN_MCP_TIMEOUT_SECONDS} seconds"
            )
        return v


class TransportTypes(Enum):
    stdio = "stdio"
    sse = "sse"


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


class StdioConfigModel(BaseConfigModel):
    command: str
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    transport_type: str = TransportTypes.stdio.value

    class Config:
        use_enum_values = True


ServerConfigModel = Union[StdioConfigModel, SseConfigModel]


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


class McpSettingsModel(BaseModel):
    mcp_servers: Dict[str, ServerConfigModel] = Field(default_factory=dict)


class ServersDetails(BaseModel):
    name: str
    status: str
    tool_count: int
    tools: Optional[List[mcp.types.Tool]]
    error: Optional[str]
    disabled: bool



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
