from typing import List

from deputydev_core.services.mcp.client import MCPClient
from deputydev_core.services.mcp.dataclass.main import (
    ServersDetails,
    ConnectionStatus,
    Tools,
)


class McpService:
    def __init__(self):
        mcp_config_path = ""
        self.mcp_client = MCPClient(mcp_config_path)

    async def sync_mcp_servers(self):
        return await self.mcp_client.sync_mcp_servers()

    async def list_tools(self, server_name):
        return await self.mcp_client.fetch_tools_list(server_name)

    async def invoke_tool(self, server_name, tool_name, tool_arguments):
        try:
            return await self.mcp_client.call_tool(
                server_name, tool_name, tool_arguments
            )
        except Exception as ex:
            return

    async def get_servers(self, limit, offset) -> List[ServersDetails]:
        servers = []
        if offset > len(self.mcp_client.connections):
            return []

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

    async def restart_server(self, server_name):
        try:
            return await self.mcp_client.restart_server(server_name)
        except Exception as ex:
            return str(ex)

    async def disable_server(self, server_name):
        try:
            return await self.mcp_client.change_status(server_name, disable=True)
        except Exception as ex:
            return str(ex)

    async def enable_server(self, server_name):
        try:
            return await self.mcp_client.change_status(server_name, disable=False)
        except Exception as ex:
            return str(ex)

    async def delete_server(self, server_name):
        try:
            return await self.mcp_client.delete_connection(server_name)
        except Exception as ex:
            return str(ex)

    async def retry_connection(self, server_name):
        try:
            return await self.mcp_client.restart_server(server_name)
        except Exception as ex:
            return str(ex)

    async def add_new_server(self, server_name):
        try:
            return await self.mcp_client.add_new_connection(server_name)
        except Exception as ex:
            return str(ex)

    async def add_remote_server(self, server_name, server_url):
        try:
            return await self.mcp_client.add_remote_server(server_name, server_url)
        except Exception as ex:
            return str(ex)
