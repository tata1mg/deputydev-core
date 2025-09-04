from abc import ABC, abstractmethod
from typing import Optional


class SessionCacheInterface(ABC):
    @abstractmethod
    async def set_session_query_id(self, session_id: int, query_id: int) -> None:
        pass

    @abstractmethod
    async def is_session_cancelled(self, session_id: int) -> bool:
        pass

    @abstractmethod
    async def cleanup_session_data(self, session_id: int) -> bool:
        pass