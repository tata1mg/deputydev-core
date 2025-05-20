import json
import os
from typing import List, Dict, Union, Any, Optional
from urllib.parse import urlparse

from deputydev_core.services.mcp.contants import DEFAULT_MCP_TIMEOUT_SECONDS
from deputydev_core.services.mcp.dataclass.main import (
    McpServer,
    ServerConfigModel,
    StdioConfigModel,
    SseConfigModel,
    ConnectionStatus,
    TransportTypes,
    McpTool,
    McpSettingsModel,
)
from deputydev_core.services.mcp.mcp_connection import McpConnection
import asyncio

from deputydev_core.services.mcp.mcp_settings import McpSettings
from fastmcp.client import Client
from fastmcp.client.transports import SSETransport, StdioTransport
from deputydev_core.utils.app_logger import AppLogger
import mcp
import pydantic
from pydantic import TypeAdapter


class MCPClient:
    _instance = None
    _init_lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MCPClient, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        mcp_config_path: str,
        tool_read_timeout_seconds: int = DEFAULT_MCP_TIMEOUT_SECONDS,
    ):
        # Prevent reinitialization
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.mcp_config_path = mcp_config_path
        self.tool_read_timeout_seconds = tool_read_timeout_seconds
        self.connections: List[McpConnection] = []
        self._initialized = True
        self.is_connecting = False
        self.mcp_settings = McpSettings(self.mcp_config_path)

    def get_servers(
        self, connection_statuses: List[ConnectionStatus]
    ) -> List[McpServer]:
        return [
            conn.server
            for conn in self.connections
            if conn.server.status in connection_statuses
        ]

    def get_active_servers(self) -> List[McpServer]:
        return [
            conn.server
            for conn in self.connections
            if conn.server.status == ConnectionStatus.connected
            and conn.server.disabled is False
        ]

    async def sync_mcp_servers(self) -> str:
        try:
            # read and validate MCP settings file
            settings: McpSettingsModel = (
                self.mcp_settings.read_and_validate_mcp_settings_file()
            )
            # update server connections
            await self.update_server_connections(settings.mcp_servers)
            return "MCP Servers connected successfully"
        except (json.JSONDecodeError, pydantic.ValidationError) as ex:
            return str(ex)

        except Exception as ex:
            return str(ex)

    async def delete_old_connections(self, servers: Dict[str, ServerConfigModel]):
        servers_to_be_deleted = {conn.server.name for conn in self.connections} - set(
            servers.keys()
        )
        # Delete server connection
        for server in servers_to_be_deleted:
            await self.delete_connection(server)

    async def restart_connection(self, server_name, server_config):
        await self.delete_connection(server_name)
        await self.connect_to_server(server_name, server_config)

    async def update_connection(
        self, server_name: str, server_config: ServerConfigModel
    ):
        current_connection = next(
            (conn for conn in self.connections if conn.server.name == server_name), None
        )
        if not current_connection:
            await self.connect_to_server(server_name, server_config)
        elif json.loads(current_connection.server.config) != server_config.model_dump():
            # Existing server with changed config
            await self.restart_connection(server_name, server_config)

    async def update_or_create_new_connections(
        self, servers: Dict[str, ServerConfigModel]
    ):
        for name, config in servers.items():
            try:
                await self.update_connection(server_name=name, server_config=config)
                AppLogger.log_debug(
                    f"Reconnected MCP server with updated config: {name}"
                )
            except Exception as ex:
                AppLogger.log_debug(f"Connection failed for MCP server: {name}")

    async def update_server_connections(self, servers: Dict[str, ServerConfigModel]):
        if self.is_connecting:
            return "MCP servers are already updating please wait for some time"
        self.is_connecting = True
        await self.delete_old_connections(servers)
        await self.update_or_create_new_connections(servers)
        self.is_connecting = False

    async def restart_server(self, server_name: str):
        connection = None
        try:
            connection = self.get_server_connection(server_name)
            config_dict = json.loads(connection.server.config)
            server_config = TypeAdapter(ServerConfigModel).validate_python(config_dict)
            await self.restart_connection(server_name, server_config=server_config)
            AppLogger.log_debug(
                f"Reconnected MCP server with updated config: {server_name}"
            )
            return f"Restarted MCP server connection for {server_name}"
        except Exception as ex:
            AppLogger.log_debug(str(ex))
            if connection:
                self.append_error_message(connection, str(ex))
            return str(ex)

    async def delete_connection(self, server_name: str) -> str:
        connection = next(
            (conn for conn in self.connections if conn.server.name == server_name), None
        )
        if connection:
            try:
                # First try to close the transport directly
                if hasattr(connection.transport, "close"):
                    await connection.transport.close()

                # Create a new task to handle the cleanup
                async def cleanup():
                    try:
                        await connection.client.__aexit__(None, None, None)
                    except Exception:
                        pass  # Ignore any errors during cleanup

                await asyncio.create_task(cleanup())
                # Remove the connection from our list
                self.connections = [
                    c for c in self.connections if c.server.name != server_name
                ]

                AppLogger.log_debug(f"Deleted MCP server: {server_name}")
                return f"Deleted MCP server connection for {server_name}"

            except Exception as error:
                AppLogger.log_error(
                    f"Failed to close transport for {server_name}: {error}"
                )
                return f"Failed to close transport for {server_name}: {error}"
        else:
            return f"Connection delete couldn't succeed as MCP server {server_name} is not connected"

    def get_server_connection(self, server_name) -> Optional[McpConnection]:
        connection = [
            conn for conn in self.connections if conn.server.name == server_name
        ]
        if connection:
            return connection[0]
        else:
            raise Exception("MCP server conncetion is not presenst")

    async def add_new_connection(self, server_name):
        server_config = self.mcp_settings.get_server_config(server_name)
        await self.update_connection(server_name, server_config)
        return f"{server_name} MCP server connected successfully"

    async def change_status(self, server_name: str, disable: bool) -> str:
        server_config = self.mcp_settings.get_server_config(server_name)
        connection = self.get_server_connection(server_name)
        connection.disable() if disable else connection.enable()
        server_config.disabled = disable
        self.mcp_settings.update_server_config(
            server_name=server_name, mcp_config=server_config
        )
        return f"MCP server {'disabled' if disable else 'enabled'} successfully"

    async def connect_to_server(
        self, name: str, config: Union[StdioConfigModel, SseConfigModel]
    ):
        # Remove existing connection if it exists
        self.connections = [
            conn for conn in self.connections if conn.server.name != name
        ]
        try:
            # Create transport
            if config.transport_type == TransportTypes.sse.value:
                transport = SSETransport(url=str(config.url))
            else:
                env = {**config.env} if config.env else {}
                if os.environ.get("PATH"):
                    env["PATH"] = os.environ.get("PATH")

                transport = StdioTransport(
                    command=config.command,
                    args=config.args or [],
                    env=env,
                )

            client = Client(transport, timeout=self.tool_read_timeout_seconds)

            connection = McpConnection(
                server=McpServer(
                    **{
                        "name": name,
                        "config": json.dumps(config.model_dump()),
                        "status": ConnectionStatus.connecting,
                        "disabled": config.disabled or False,
                        "error": "",
                        "tools": None,
                        "resources": None,
                        "resource_templates": None,
                    }
                ),
                client=client,
                transport=transport,
            )
            self.connections.append(connection)
            client = await client.__aenter__()
            connection.server.status = ConnectionStatus.connected
            connection.server.error = ""
            connection.server.tools = await client.list_tools()

        except Exception as error:
            # Update status with error
            connection = next(
                (conn for conn in self.connections if conn.server.name == name), None
            )
            if connection:
                connection.server.status = ConnectionStatus.disconnected
                self.append_error_message(connection, str(error))
            raise error

    def append_error_message(self, connection: McpConnection, error: str):
        new_error = (
            f"{connection.server.error}\n{error}" if connection.server.name else error
        )
        connection.server.error = new_error

    async def fetch_tools_list(self, server_name: str) -> Union[List[McpTool], str]:
        tools = []
        try:
            connection = next(
                (conn for conn in self.connections if conn.server.name == server_name),
                None,
            )
            if not connection:
                return f"No connection found for server: {server_name}"
            if connection.client.is_connected():
                tools = await connection.client.list_tools()
        except Exception as error:
            AppLogger.log_error(f"Failed to fetch tools for {server_name}: {error}")
            return f"Failed to fetch tools for {server_name}: {error}"
        finally:
            return tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        tool_arguments: Optional[Dict[str, Any]] = None,
    ) -> mcp.types.CallToolResult:
        connection = next(
            (conn for conn in self.connections if conn.server.name == server_name), None
        )
        if not connection:
            raise Exception(
                f"No connection found for server: {server_name}."
                f" Please make sure to use MCP servers available under 'Connected MCP Servers'."
            )

        if connection.server.disabled:
            raise Exception(f'Server "{server_name}" is disabled and cannot be used')

        try:
            tool_response = await connection.client.call_tool_mcp(
                name=tool_name, arguments=tool_arguments
            )
            return tool_response
        except Exception as error:
            print(
                f"Failed to parse timeout configuration for server {server_name}: {error}"
            )

    async def add_remote_server(self, server_name: str, server_url: str) -> str:
        try:
            settings = self.mcp_settings.read_and_validate_mcp_settings_file()
            if not settings:
                raise Exception("Failed to read MCP settings")

            if server_name in settings.mcp_servers:
                raise Exception(
                    f'An MCP server with the name "{server_name}" already exists'
                )
            try:
                urlparse(server_url)
                if not server_url.startswith(("http://", "https://")):
                    raise ValueError("URL must start with http:// or https://")
            except Exception:
                raise Exception(
                    f"Invalid server URL: {server_url}. Please provide a valid URL."
                )

            server_config = SseConfigModel(
                url=server_url, disabled=False, auto_approve=[]
            )

            # Update the config object
            settings.mcp_servers[server_name] = server_config

            basic_config = SseConfigModel(
                auto_approve=[], disabled=False, url=server_url
            )
            self.mcp_settings.update_server_config(
                server_name=server_name, mcp_config=basic_config
            )
            await self.connect_to_server(name=server_name, config=basic_config)
            return f"Added remote MCP server: {server_name}"

        except Exception as error:
            AppLogger.log_error(f"Failed to add remote MCP server: {error}")
            return f"Failed to add remote MCP server: {error}"

    async def dispose(self):
        AppLogger.log_debug("started disposing MCP servers")
        for conn in self.connections:
            await self.delete_connection(conn.server.name)
            await asyncio.sleep(0.2)
        AppLogger.log_debug("exit disposing MCP servers")
