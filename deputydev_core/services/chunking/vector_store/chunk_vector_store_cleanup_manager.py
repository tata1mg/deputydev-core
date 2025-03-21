import time
from datetime import datetime, timedelta, timezone
from typing import List

from deputydev_core.services.repository.chunk_files_service import ChunkFilesService
from deputydev_core.services.repository.chunk_service import ChunkService
from deputydev_core.services.repository.dataclasses.main import WeaviateSyncAndAsyncClients
from deputydev_core.utils.app_logger import AppLogger


class ChunkVectorStoreCleaneupManager:
    def __init__(
        self,
        exclusion_chunk_hashes: List[str],
        weaviate_client: WeaviateSyncAndAsyncClients,
    ):
        self.exclusion_chunk_hashes = exclusion_chunk_hashes
        self.weaviate_client = weaviate_client
        self.last_used_at_timedelta = timedelta(days=30)

    async def _cleanup_chunk_and_chunk_files_objects(self, last_used_lt: datetime) -> None:
        time_start = time.perf_counter()
        try:
            ChunkService(weaviate_client=self.weaviate_client).cleanup_old_chunks(
                last_used_lt=last_used_lt,
                exclusion_chunk_hashes=self.exclusion_chunk_hashes,
            )
            ChunkFilesService(weaviate_client=self.weaviate_client).cleanup_old_chunk_files(
                last_used_lt=last_used_lt,
                exclusion_chunk_hashes=self.exclusion_chunk_hashes,
            )
            AppLogger.log_debug(f"Cleaning up took {time.perf_counter() - time_start} seconds")
        except Exception as _ex:
            AppLogger.log_debug(message=str(_ex))

    async def start_cleanup_for_chunk_and_hashes(
        self,
    ) -> None:
        try:
            await self._cleanup_chunk_and_chunk_files_objects(
                last_used_lt=datetime.now().replace(tzinfo=timezone.utc) - self.last_used_at_timedelta
            )
        except Exception as _ex:
            AppLogger.log_debug(message=str(_ex))
