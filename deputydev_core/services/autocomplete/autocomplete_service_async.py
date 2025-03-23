from abc import ABC, abstractmethod
import time
from typing import List, Any

from deputydev_core.models.dto.chunk_file_dto import ChunkFileDTO
from deputydev_core.services.autocomplete.dataclasses.main import AutoCompleteSearch, SearchPath
from deputydev_core.utils.app_logger import AppLogger


class AutoCompleteServiceAsync(ABC):
    @abstractmethod
    async def _build_filters(self, search_paths: List[SearchPath]) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def _fuzzy_search(self,  request: AutoCompleteSearch) -> List[ChunkFileDTO]:
        raise NotImplementedError

    async def keyword_suggestions(self, request: AutoCompleteSearch) -> List[ChunkFileDTO]:
        start_time = time.time()
        suggestions = await self._fuzzy_search(request)
        elapsed_time = time.time() - start_time
        AppLogger.log_info(f"Code search completed in {elapsed_time:.4f} seconds")
        return suggestions
