from functools import wraps
from typing import Callable, Dict, Any, Optional, Awaitable


def handle_response_headers(func: Callable[..., Awaitable[Dict[str, Any]]]) -> Callable[
    ..., Awaitable[Optional[Dict[str, Any]]]]:
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Optional[Dict[str, Any]]:
        result, response_headers = await func(*args, **kwargs)
        if response_headers.get("new_session_data"):
            print(response_headers.get("new_session_data"))
        return result

    return wrapper
