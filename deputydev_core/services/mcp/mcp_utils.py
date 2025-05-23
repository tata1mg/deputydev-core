from functools import wraps
from deputydev_core.services.mcp.dataclass.main import McpResponse, McpResponseMeta


def handle_exceptions_async(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return McpResponse(is_error=False, data=result)
        except Exception as ex:
            return McpResponse(is_error=True, meta=McpResponseMeta(message=str(ex)))

    return wrapper
