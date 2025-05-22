from typing import List

from deputydev_core.services.mcp.client import MCPClient
from deputydev_core.services.mcp.contants import MAX_CHARACTERS_TO_RETURN
from deputydev_core.services.mcp.dataclass.main import (
    ServersDetails,
    ConnectionStatus,
    Tools, ToolInvokeRequest,
)
import mcp

from deputydev_core.services.mcp.mcp_utils import handle_exceptions_async
from mcp.types import TextContent


class McpService:
    def __init__(self):
        self.mcp_client = MCPClient()

    @handle_exceptions_async
    async def sync_mcp_servers(self, mcp_config_path: str):
        await self.mcp_client.sync_mcp_servers(mcp_config_path)
        # TODO handle pagination
        return await self.get_servers(limit=-1, offset=0)

    @handle_exceptions_async
    async def list_tools(self, server_name):
        return await self.mcp_client.fetch_tools_list(server_name)

    async def invoke_tool(self,  tool_invoke_request: ToolInvokeRequest) -> mcp.types.CallToolResult:
        try:
            tool_response = await self.mcp_client.call_tool(
                server_name = tool_invoke_request.server_name,
                tool_name = tool_invoke_request.tool_name,
                tool_arguments = tool_invoke_request.tool_arguments
            )
            # limit max characters to return from tool response
            if tool_response and tool_response.content and isinstance(tool_response.content[0], TextContent):
                tool_response.content[0].text = tool_response.content[0].text[:MAX_CHARACTERS_TO_RETURN]
        except Exception as ex:
            return mcp.types.CallToolResult(
                isError=True,
                content=[
                    mcp.types.TextContent(
                        type="text",
                        text=f"Error: {str(ex)[:MAX_CHARACTERS_TO_RETURN]}"
                    )
                ]
            )

    @handle_exceptions_async
    async def get_servers(self, limit, offset):
        servers = []
        if offset > len(self.mcp_client.connections):
            return []
        if limit == -1:
            limit = len(self.mcp_client.connections)

        connection_statuses = list(ConnectionStatus)
        eligible_servers = self.mcp_client.get_servers(
            connection_statuses=connection_statuses
        )[offset : offset + limit]
        for server in eligible_servers:
            servers.append(
                ServersDetails(
                    name=server.name,
                    status=server.status.value,
                    tool_count=len(server.tools) if server.tools else 0,
                    tools=server.tools if server.tools else [],
                    error=server.error,
                    disabled=server.disabled,
                )
            )
        return servers

    @handle_exceptions_async
    async def get_eligible_tools(
        self,
        max_allowed_tools_per_server=40,
        max_allowed_servers=40,
        max_allowed_tools=1000,
    ) -> List[ServersDetails]:
        servers: List[ServersDetails] = []
        total_tools = 0
        for server in self.mcp_client.get_active_servers()[:max_allowed_servers]:
            current_tools = server.tools[:max_allowed_tools_per_server]
            if total_tools + len(current_tools) < max_allowed_tools:
                servers.append(
                    Tools(
                        server_name=server.name,
                        tools=current_tools,
                    )
                )
                total_tools += len(server.tools)
        return servers

    @handle_exceptions_async
    async def restart_server(self, server_name):
        return await self.mcp_client.restart_server(server_name)

    @handle_exceptions_async
    async def disable_server(self, server_name):
        return await self.mcp_client.change_status(server_name, disable=True)

    @handle_exceptions_async
    async def enable_server(self, server_name):
        return await self.mcp_client.change_status(server_name, disable=False)

    @handle_exceptions_async
    async def delete_server(self, server_name):
        return await self.mcp_client.delete_connection(server_name)

    @handle_exceptions_async
    async def retry_connection(self, server_name):
        return await self.mcp_client.restart_server(server_name)

    @handle_exceptions_async
    async def add_new_server(self, server_name):
        return await self.mcp_client.add_new_connection(server_name)

    @handle_exceptions_async
    async def add_remote_server(self, server_name, server_url):
        return await self.mcp_client.add_remote_server(server_name, server_url)
