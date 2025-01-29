import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from repository.chunk_service import ChunkService
from repository.chunk_files_service import ChunkFilesService
from repository.chunk_usages_service import ChunkUsagesService
from repository.dataclasses.main import WeaviateSyncAndAsyncClients


class ChunkVectorStoreCleaneupManager:
    def __init__(
            self,
            exclusion_chunk_hashes: List[str],
            weaviate_client: WeaviateSyncAndAsyncClients,
            usage_hash: Optional[str] = None,
    ):
        self.exclusion_chunk_hashes = exclusion_chunk_hashes
        self.weaviate_client = weaviate_client
        self.last_used_at_timedelta = timedelta(minutes=3)
        self.usage_hash = usage_hash

    async def _cleanup_chunk_and_chunk_files_objects(self, chunk_hashes_to_clean: List[str]) -> None:
        time_start = time.perf_counter()
        try:
            ChunkService(weaviate_client=self.weaviate_client).cleanup_old_chunks(
                chunk_hashes_to_clean=chunk_hashes_to_clean,
            )
            ChunkFilesService(weaviate_client=self.weaviate_client).cleanup_old_chunk_files(
                chunk_hashes_to_clean=chunk_hashes_to_clean,
            )
        except Exception as _ex:
            pass

    async def start_cleanup_for_chunk_and_hashes(
            self,
    ) -> None:
        try:
            chunk_hashes_to_clean = ChunkUsagesService(weaviate_client=self.weaviate_client).get_removable_chunk_hashes(
                last_used_lt=datetime.now().replace(tzinfo=timezone.utc) - self.last_used_at_timedelta,
                chunk_hashes_to_skip=self.exclusion_chunk_hashes,
                chunk_usage_hash_to_skip=[self.usage_hash] if self.usage_hash else [],
            )
            await self._cleanup_chunk_and_chunk_files_objects(chunk_hashes_to_clean=chunk_hashes_to_clean)
        except Exception as _ex:
            pass
