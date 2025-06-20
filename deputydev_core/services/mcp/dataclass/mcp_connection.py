from typing import Union

from fastmcp import Client
from fastmcp.client.transports import SSETransport, StdioTransport

from deputydev_core.services.mcp.dataclass.main import McpServer


class McpConnection:
    def __init__(
        self,
        server: McpServer,
        client: Client,
        transport: Union[SSETransport, StdioTransport],
    ):
        self.server = server
        self.client = client
        self.transport = transport

    def enable(self):
        self.server.disabled = False

    def disable(self):
        self.server.disabled = True
