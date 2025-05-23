from typing import List

from deputydev_core.services.mcp.client import MCPClient
from deputydev_core.services.mcp.dataclass.main import (
    ServersDetails,
    ConnectionStatus,
    Tools, ToolInvokeRequest,
)
import mcp

from deputydev_core.services.mcp.mcp_utils import handle_exceptions_async


class McpService:
    def __init__(self):
        self.mcp_client = MCPClient()

    @handle_exceptions_async
    async def sync_mcp_servers(self, mcp_config_path: str):
        await self.mcp_client.sync_mcp_servers(mcp_config_path)
        # TODO handle pagination
        return await self.create_server_list(limit=-1, offset=0)

    @handle_exceptions_async
    async def list_tools(self, server_name):
        return await self.mcp_client.fetch_tools_list(server_name)

    async def invoke_tool(self,  tool_invoke_request: ToolInvokeRequest) -> mcp.types.CallToolResult:
        try:
            return await self.mcp_client.call_tool(
                server_name = tool_invoke_request.server_name,
                tool_name = tool_invoke_request.tool_name,
                tool_arguments = tool_invoke_request.tool_arguments
            )
        except Exception as ex:
            return mcp.types.CallToolResult(
                isError=True,
                content=[
                    mcp.types.TextContent(
                        type="text",
                        text=f"Error: {str(ex)}"
                    )
                ]
            )

    async def create_server_list(self, limit, offset):
        servers = []
        if offset > len(self.mcp_client.connections):
            return []
        if limit == -1:
            limit = len(self.mcp_client.connections)

        connection_statuses = list(ConnectionStatus)
        eligible_servers = self.mcp_client.get_servers(
            connection_statuses=connection_statuses
        )[offset: offset + limit]
        for server in eligible_servers:
            servers.append(
                ServersDetails(
                    name=server.name,
                    status=server.status.value,
                    tool_count=len(server.tools) if server.tools else 0,
                    tools=server.tools if server.tools else [],
                    error=server.error,
                    disabled=server.disabled,
                    auto_approve=server.auto_approve
                )
            )
        return servers

    @handle_exceptions_async
    async def get_servers(self, limit, offset):
        await self.create_server_list(limit, offset)

    @handle_exceptions_async
    async def get_eligible_tools(self) -> List[Tools]:
        return await self.mcp_client.get_tools()

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
