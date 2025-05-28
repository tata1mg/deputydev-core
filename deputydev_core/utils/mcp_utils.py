from functools import wraps
from typing import List

from deputydev_core.services.mcp.dataclass.main import (
    McpResponse,
    McpResponseMeta,
    McpServer,
)
from deputydev_core.services.mcp.dataclass.mcp_connection import McpConnection


def handle_exceptions_async(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return McpResponse(is_error=False, data=result)
        except Exception as ex:
            return McpResponse(is_error=True, meta=McpResponseMeta(message=str(ex)))

    return wrapper


def get_sorted_connection_order(
    servers: List[str], connections: List[McpServer]
) -> List[McpServer]:
    if not servers:
        return connections
    # Build an index map for fast lookup
    name_order = {name: index for index, name in enumerate(servers)}
    return sorted(connections, key=lambda s: name_order.get(s.name, float("inf")))
