import asyncio
import json
import os
import traceback
from typing import Any, Dict, List, Optional, OrderedDict

from fastmcp.client import Client
from fastmcp.client.transports import (
    SSETransport,
    StdioTransport,
    StreamableHttpTransport,
)
from mcp.types import CallToolResult, Tool
from pydantic import Field

from deputydev_core.services.mcp.dataclass.main import (
    ConnectionStatus,
    ExtendedTool,
    McpDefaultSettings,
    McpServer,
    McpSettingsModel,
    ServerConfigModel,
    Tools,
    Transports,
    TransportTypes,
)
from deputydev_core.services.mcp.dataclass.mcp_connection import McpConnection
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.mcp_settings import McpSettings
from deputydev_core.utils.mcp_utils import get_sorted_connection_order


class MCPClient:
    _instance = None
    _init_lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MCPClient, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def get_instance(cls, mcp_config_path: str, default_settings: McpDefaultSettings):
        if cls._instance is None:
            if cls._init_lock is None:
                cls._init_lock = asyncio.Lock()

            async with cls._init_lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = cls(mcp_config_path, default_settings)
        return cls._instance

    def __init__(self, mcp_config_path: str, default_settings: McpDefaultSettings):
        # Prevent reinitialization
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.connections: List[McpConnection] = []
        self._initialized = True
        self.is_connecting = False
        self.mcp_config_path = mcp_config_path
        self.mcp_settings = McpSettings(self.mcp_config_path)
        self.default_settings = default_settings
        self.configured_servers: OrderedDict[str, ServerConfigModel] = Field(default_factory=OrderedDict)

    def get_servers(self, connection_statuses: List[ConnectionStatus]) -> List[McpServer]:
        _servers = [conn.server for conn in self.connections if conn.server.status in connection_statuses]
        servers_from_settings = list(self.configured_servers.keys())
        return get_sorted_connection_order(servers=servers_from_settings, connections=_servers)

    def get_active_servers(self) -> List[McpServer]:
        _servers = [
            conn.server
            for conn in self.connections
            if conn.server.status == ConnectionStatus.connected and conn.server.disabled is False
        ]
        servers_from_settings = list(self.configured_servers.keys())
        return get_sorted_connection_order(servers=servers_from_settings, connections=_servers)

    async def sync_mcp_servers(self) -> str:
        # update server connections
        settings: McpSettingsModel = self.mcp_settings.read_and_validate_mcp_settings_file()
        self.configured_servers = settings.mcp_servers
        if not settings:
            if self.connections:
                for con in self.connections:
                    await self.delete_connection(con.server.name)
            return "No MCP servers are configured"
        await self._update_server_connections(settings.mcp_servers)
        return "MCP Servers connected successfully"

    async def delete_old_connections(self, servers: Dict[str, ServerConfigModel]):
        servers_to_be_deleted = {conn.server.name for conn in self.connections} - set(servers.keys())
        # Delete server connection
        for server in servers_to_be_deleted:
            await self.delete_connection(server)

    async def restart_connection(self, server_name, server_config):
        await self.delete_connection(server_name)
        await asyncio.sleep(1)
        await self._connect_to_server(server_name, server_config)

    async def update_connection(self, server_name: str, server_config: ServerConfigModel):
        current_connection = next((conn for conn in self.connections if conn.server.name == server_name), None)
        if not current_connection:
            await self._connect_to_server(server_name, server_config)
            AppLogger.log_debug(f"Connected to MCP server : {server_name}")
        elif json.loads(current_connection.server.config) != server_config.model_dump():
            # Existing server with changed config
            await self.restart_connection(server_name, server_config)
            AppLogger.log_debug(f"Reconnected MCP server with updated config: {server_name}")

    async def update_or_create_new_connections(self, servers: Dict[str, ServerConfigModel]):
        for name, config in servers.items():
            try:
                await self.update_connection(server_name=name, server_config=config)
            except Exception as ex:
                print(traceback.format_exc())
                AppLogger.log_debug(f"Connection failed for MCP server: {name} {str(ex)}")

    async def _update_server_connections(self, servers: Dict[str, ServerConfigModel]):
        self.is_connecting = True
        await self.delete_old_connections(servers)
        await self.update_or_create_new_connections(servers)
        self.is_connecting = False

    async def restart_server(self, server_name: str):
        connection = None
        try:
            connection = self.get_server_connection(server_name)
            server_config = self.mcp_settings.get_server_config(server_name)
            await self.restart_connection(server_name, server_config=server_config)
            AppLogger.log_debug(f"Reconnected MCP server with updated config: {server_name}")
            return f"Restarted MCP server connection for {server_name}"
        except Exception as ex:
            AppLogger.log_debug(str(ex))
            if connection:
                self.append_error_message(connection, str(ex))
            return str(ex)

    async def delete_connection(self, server_name: str, remove_connection_from_list: bool = True) -> str:
        connection = next((conn for conn in self.connections if conn.server.name == server_name), None)
        if connection and connection.server.status == ConnectionStatus.connected:
            try:
                # Create a new task to handle the cleanup
                async def cleanup():
                    try:
                        await connection.client.__aexit__(None, None, None)
                    except Exception:
                        pass  # Ignore any errors during cleanup

                try:
                    # wait for max 5 seconds to cancel the task
                    await asyncio.wait_for(asyncio.shield(cleanup()), timeout=5)
                except asyncio.TimeoutError:
                    AppLogger.log_debug(f"Cleanup task for {server_name} timed out.")
                except asyncio.CancelledError:
                    AppLogger.log_debug(f"Cleanup task for {server_name} was cancelled externally.")
                except Exception:
                    AppLogger.log_debug(f"Cleanup task for {server_name} was failed.")

            except Exception as error:
                AppLogger.log_error(f"Failed to close transport for {server_name}: {error}")
                return f"Failed to close transport for {server_name}: {error}"

        if remove_connection_from_list:
            self.connections = [c for c in self.connections if c.server.name != server_name]
        # Remove the connection from our list
        AppLogger.log_debug(f"Deleted MCP server: {server_name}")
        return f"Deleted MCP server connection for {server_name}"

    def get_server_connection(self, server_name) -> Optional[McpConnection]:
        connection = [conn for conn in self.connections if conn.server.name == server_name]
        if connection:
            return connection[0]
        else:
            raise Exception("MCP server connection is not present")

    async def add_new_connection(self, server_name):
        server_config = self.mcp_settings.get_server_config(server_name)
        await self.update_connection(server_name, server_config)
        return f"{server_name} MCP server connected successfully"

    async def change_status(self, server_name: str, disable: bool) -> str:
        server_config = self.mcp_settings.get_server_config(server_name)
        server_config.disabled = disable
        self.mcp_settings.update_server_config(server_name=server_name, mcp_config=server_config)
        connection = self.get_server_connection(server_name)
        connection.disable() if disable else connection.enable()
        if disable:
            await self.delete_connection(server_name, remove_connection_from_list=False)
            connection.server.status = ConnectionStatus.disconnected
        else:
            connection.server.status = ConnectionStatus.connecting
            client = await connection.client.__aenter__()
            server_tools = await client.list_tools()
            connection.server.tools = self.populate_server_tools(server_tools, server_config=server_config)
            connection.server.status = ConnectionStatus.connected
        return f"MCP server {'disabled' if disable else 'enabled'} successfully"

    def get_default_settings(self) -> McpDefaultSettings:
        settings: McpSettingsModel = self.mcp_settings.read_and_validate_mcp_settings_file()

        if not settings.default_settings:
            return self.default_settings

        return self.default_settings.copy(
            update={k: v for k, v in settings.default_settings.dict(exclude_unset=True).items()}
        )

    def _create_mcp_client(self, transport: Transports, connection_timeout: int) -> Client:
        if not isinstance(transport, Transports):
            raise Exception(f"Unsupported transport type {transport.__class__.__name__}")

        client = Client(transport, timeout=connection_timeout)
        return client

    async def _connect_to_server(self, name: str, config: ServerConfigModel):
        # Remove existing connection if it exists
        self.connections = [conn for conn in self.connections if conn.server.name != name]
        try:
            default_settings = self.get_default_settings()
            connection_timeout = config.connection_timeout or default_settings.connection_timeout
            read_timeout = config.read_timeout or default_settings.read_timeout

            if config.transport_type == TransportTypes.sse.value:
                transport = SSETransport(url=config.url, sse_read_timeout=read_timeout)
            elif config.transport_type == TransportTypes.streamable_http.value:
                transport = StreamableHttpTransport(url=config.url, sse_read_timeout=read_timeout)
            else:
                env = {**config.env} if config.env else {}
                if os.environ.get("PATH"):
                    env["PATH"] = os.environ.get("PATH")

                transport = StdioTransport(
                    command=config.command,
                    args=config.args or [],
                    env=env,
                )

            client = self._create_mcp_client(transport=transport, connection_timeout=connection_timeout)

            connection = McpConnection(
                server=McpServer(
                    **{
                        "name": name,
                        "config": json.dumps(config.model_dump()),
                        "status": ConnectionStatus.connecting,
                        "disabled": config.disabled if config.disabled is not None else False,
                        "error": "",
                        "tools": None,
                        "read_timeout": read_timeout,
                    }
                ),
                client=client,
                transport=transport,
            )
            self.connections.append(connection)
            if not config.disabled:
                client = await client.__aenter__()
                connection.server.status = ConnectionStatus.connected
                server_tools = await client.list_tools()
                connection.server.tools = self.populate_server_tools(server_tools, server_config=config)
            else:
                connection.server.status = ConnectionStatus.disconnected

        except Exception as error:
            # Update status with error
            connection = next((conn for conn in self.connections if conn.server.name == name), None)
            if connection:
                connection.server.status = ConnectionStatus.disconnected
                error_message = str(error)
                if not error_message:
                    error_message = (
                        f"Couldn't connected to MCP server : {connection.server.name} "
                        f"error {error.__class__.__name__} or TimeoutError"
                        f". If you are using docker please check docker is up and running."
                    )
                self.append_error_message(connection, error_message)
            raise error

    def append_error_message(self, connection: McpConnection, error: str):
        connection.server.error = error

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        tool_arguments: Optional[Dict[str, Any]] = None,
    ) -> CallToolResult:
        connection = next((conn for conn in self.connections if conn.server.name == server_name), None)
        if not connection:
            raise Exception(
                f"No connection found for server: {server_name}."
                f" Please make sure to use MCP servers available under 'Connected MCP Servers'."
            )

        if connection.server.disabled:
            raise Exception(f'Server "{server_name}" is disabled and cannot be used')

        try:
            tool_response = await connection.client.call_tool_mcp(
                name=tool_name,
                arguments=tool_arguments,
                timeout=connection.server.read_timeout,
            )
            return tool_response
        except Exception as error:
            AppLogger.log_debug(f"Failed to parse timeout configuration for server {server_name}: {error}")
            raise Exception(f"Failed to parse timeout configuration for server {server_name}: {error}")

    async def dispose(self):
        AppLogger.log_debug("started disposing MCP servers")
        for conn in self.connections:
            await self.delete_connection(conn.server.name)
            await asyncio.sleep(0.2)
        AppLogger.log_debug("exit disposing MCP servers")

    async def get_tools(self) -> List[Tools]:
        max_tools = self.get_default_settings().max_tools
        tools: List[Tools] = []
        total_tools = 0

        for server in self.get_active_servers():
            current_tools = server.tools
            if total_tools + len(current_tools) < max_tools:
                tools.append(
                    Tools(
                        server_name=server.name,
                        tools=current_tools,
                    )
                )
                total_tools += len(server.tools)
        return tools

    async def approve_tool(self, server_name: str, tool_name: str):
        connection = self.get_server_connection(server_name)
        tool = [tool for tool in connection.server.tools if tool.name == tool_name] or None
        if not tool:
            raise Exception(f"Tool not found Tool Name: {tool_name} for server: {server_name}")
        tool = tool[0]
        tool.auto_approve = True
        json_config = self.mcp_settings.get_server_config(server_name)
        json_config.auto_approve_tools.append(tool_name)
        self.mcp_settings.update_server_config(server_name, json_config)
        return "Tool approved successfully"

    def populate_server_tools(self, tools: List[Tool], server_config: ServerConfigModel) -> List[ExtendedTool]:
        processed_tools: List[ExtendedTool] = []
        for tool in tools:
            server_config.auto_approve_tools = server_config.auto_approve_tools or []
            auto_approve = server_config.auto_approve_tools == "all" or tool.name in server_config.auto_approve_tools
            processed_tools.append(ExtendedTool(**tool.model_dump(), auto_approve=auto_approve))
        return processed_tools
