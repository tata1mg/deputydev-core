import json
import os
from typing import List, Dict, Union, Any, Optional
from urllib.parse import urlparse
from deputydev_core.services.mcp.dataclass.main import (
    McpServer,
    ServerConfigModel,
    SseConfigModel,
    ConnectionStatus,
    TransportTypes,
    McpTool,
    McpSettingsModel, Transports, DefaultSettings, Tools,
)
from deputydev_core.services.mcp.mcp_connection import McpConnection
import asyncio

from deputydev_core.services.mcp.mcp_settings import McpSettings
from fastmcp.client import Client
from fastmcp.client.transports import SSETransport, StdioTransport, StreamableHttpTransport
from deputydev_core.utils.app_logger import AppLogger
import mcp
from pydantic import TypeAdapter


class MCPClient:
    _instance = None
    _init_lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MCPClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent reinitialization
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.connections: List[McpConnection] = []
        self._initialized = True
        self.is_connecting = False
        self.mcp_config_path = None
        self.mcp_settings = None

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

    def init(self, mcp_config_path:  str):
        self.mcp_config_path = mcp_config_path
        self.mcp_settings = McpSettings(self.mcp_config_path)
        # read and validate MCP settings file

    async def sync_mcp_servers(self, mcp_config_path: str = None) -> str:
        self.init(mcp_config_path)
        # update server connections
        settings: McpSettingsModel = (
            self.mcp_settings.read_and_validate_mcp_settings_file()
        )
        if not settings:
            if self.connections:
                for con in self.connections:
                    await self.delete_connection(con.server.name)
            return "No MCP servers are configured"
        await self.update_server_connections(settings.mcp_servers)
        return "MCP Servers connected successfully"

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
            AppLogger.log_debug(
                f"Connected to MCP server : {server_name}"
            )
        elif json.loads(current_connection.server.config) != server_config.model_dump():
            # Existing server with changed config
            await self.restart_connection(server_name, server_config)
            AppLogger.log_debug(
                f"Reconnected MCP server with updated config: {server_name}"
            )

    async def update_or_create_new_connections(
        self, servers: Dict[str, ServerConfigModel]
    ):
        for name, config in servers.items():
            try:
                await self.update_connection(server_name=name, server_config=config)
            except Exception as ex:
                AppLogger.log_debug(f"Connection failed for MCP server: {name} {str(ex)}")

    async def update_server_connections(self, servers: Dict[str, ServerConfigModel]):
        # TODO need to hand the multiple sync servers call better
        # if self.is_connecting:
        #     return "MCP servers are already updating please wait for some time"
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
            raise Exception(f"Couldn't deleted MCP server {server_name} because it is not connected")

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

    def get_default_settings(self) -> DefaultSettings:
        settings: McpSettingsModel = self.mcp_settings.read_and_validate_mcp_settings_file()
        return settings.default_settings


    def create_mcp_client(self, transport: Transports, connection_timeout: int) -> Client:
        if not isinstance(transport, Transports):
            raise Exception(f"Unsupported transport type {transport.__class__.__name__}")

        client = Client(transport, timeout=connection_timeout)
        return client


    async def connect_to_server(self, name: str, config: ServerConfigModel):
        # Remove existing connection if it exists
        self.connections = [
            conn for conn in self.connections if conn.server.name != name
        ]

        try:
            default_settings = self.get_default_settings()
            connection_timeout = config.connection_timeout or default_settings.connection_timeout
            read_timeout = config.read_timeout or default_settings.read_timeout
            auto_approve = config.auto_approve or default_settings.auto_approve

            if config.transport_type == TransportTypes.sse.value:
                transport = SSETransport(url=str(config.url), sse_read_timeout = read_timeout)
            elif config.transport_type == TransportTypes.streamable_http.value:
                transport = StreamableHttpTransport(url=str(config.url), sse_read_timeout = read_timeout)
            else:
                env = {**config.env} if config.env else {}
                if os.environ.get("PATH"):
                    env["PATH"] = os.environ.get("PATH")

                transport = StdioTransport(
                    command=config.command,
                    args=config.args or [],
                    env=env,
                )

            client = self.create_mcp_client(transport=transport,
                                                                        connection_timeout=connection_timeout)

            connection = McpConnection(
                server=McpServer(
                    **{
                        "name": name,
                        "config": json.dumps(config.model_dump()),
                        "status": ConnectionStatus.connecting,
                        "disabled": config.disabled if config.disabled is not None else False,
                        "error": "",
                        "tools": None,
                        "resources": None,
                        "resource_templates": None,
                        "read_timeout":read_timeout,
                        "auto_approve":auto_approve
                    }
                ),
                client=client,
                transport=transport
            )
            self.connections.append(connection)
            client = await client.__aenter__()
            connection.server.status = ConnectionStatus.connected
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
                name=tool_name, arguments=tool_arguments, timeout=connection.server.read_timeout
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
