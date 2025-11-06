import asyncio
from datetime import datetime
from typing import List, Optional, Tuple

from weaviate.classes.query import Filter, MetadataQuery
from weaviate.util import generate_uuid5

from deputydev_core.models.dao.weaviate.chunks import Chunks
from deputydev_core.models.dto.chunk_dto import (
    ChunkDTO,
    ChunkDTOWithScore,
    ChunkDTOWithVector,
)
from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.repository.base_weaviate_repository import (
    BaseWeaviateRepository,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.utils.app_logger import AppLogger


class ChunkService(BaseWeaviateRepository):
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients) -> None:
        super().__init__(weaviate_client, Chunks.collection_name)

    async def perform_filtered_vector_hybrid_search(
        self,
        chunk_hashes: List[str],
        query: str,
        query_vector: List[float],
        limit: int = 20,
        alpha: float = 0.7,
    ) -> List[ChunkDTOWithScore]:
        try:
            await self.ensure_collection_connections()
            all_chunks = await self.async_collection.query.hybrid(
                filters=Filter.by_property("chunk_hash").contains_any(chunk_hashes),
                query=query,
                limit=limit,
                vector=query_vector,
                alpha=alpha,
                return_metadata=MetadataQuery(score=True),
            )
            return [
                ChunkDTOWithScore(
                    score=chunk_file_obj.metadata.score,
                    chunk=ChunkDTO(
                        **chunk_file_obj.properties,
                        id=str(chunk_file_obj.uuid),
                    ),
                )
                for chunk_file_obj in all_chunks.objects
            ]
        except Exception as ex:
            AppLogger.log_error("Failed to get chunk files by commit hashes")
            raise ex

    async def get_chunks_by_chunk_hashes(
        self, chunk_hashes: List[str], with_vector: bool = False
    ) -> List[Tuple[ChunkDTO, List[float]]]:
        batch_size = 1000
        all_chunks: List[Tuple[ChunkDTO, List[float]]] = []
        max_results_per_query = 10000
        try:
            await self.ensure_collection_connections()
            # Process chunk hashes in batches
            for i in range(0, len(chunk_hashes), batch_size):
                batch_hashes = chunk_hashes[i : i + batch_size]
                batch_chunks = await self.async_collection.query.fetch_objects(
                    filters=Filter.any_of(
                        [Filter.by_id().equal(generate_uuid5(chunk_hash)) for chunk_hash in batch_hashes]
                    ),
                    include_vector=with_vector,
                    limit=max_results_per_query,
                )
                # Break if no more results
                if batch_chunks.objects:
                    # Convert to DTOs efficiently using list comprehension
                    batch_dtos = [
                        (
                            ChunkDTO(**chunk_obj.properties, id=str(chunk_obj.uuid)),
                            chunk_obj.vector.get("default") or [],
                        )
                        for chunk_obj in batch_chunks.objects
                    ]
                    all_chunks.extend(batch_dtos)

            return all_chunks

        except Exception as ex:
            AppLogger.log_error(
                f"Failed to get chunk files by commit hashes chunk_hashes_count: {len(chunk_hashes)}, error: {str(ex)}"
            )
            raise

    async def bulk_insert(self, chunks: List[ChunkDTOWithVector]) -> None:
        await self.ensure_collection_connections()
        with self.sync_collection.batch.dynamic() as _batch:
            for chunk in chunks:
                properties = chunk.dto.model_dump(mode="json", exclude={"id"})
                uuid = generate_uuid5(chunk.dto.chunk_hash)

                # Only include vector if it’s non-empty and valid
                if chunk.vector and len(chunk.vector) > 0:
                    _batch.add_object(
                        properties=properties,
                        vector=chunk.vector,
                        uuid=uuid,
                    )
                else:
                    # Insert without vector
                    _batch.add_object(
                        properties=properties,
                        uuid=uuid,
                    )

    async def cleanup_old_chunks(self, last_used_lt: datetime, exclusion_chunk_hashes: List[str]) -> None:
        await self.ensure_collection_connections()
        batch_size = 1000
        while True:
            deletable_objects = self.sync_collection.query.fetch_objects(
                limit=batch_size,
                filters=Filter.all_of(
                    [
                        *[
                            Filter.by_id().not_equal(generate_uuid5(chunk_hash))
                            for chunk_hash in exclusion_chunk_hashes
                        ],
                        Filter.by_property("created_at").less_than(last_used_lt),
                    ]
                ),
            )

            AppLogger.log_debug(f"{len(deletable_objects.objects)} chunks to be deleted in batch")

            if len(deletable_objects.objects) <= 0:
                break

            result = self.sync_collection.data.delete_many(
                Filter.any_of(
                    [Filter.by_id().equal(obj.uuid) for obj in deletable_objects.objects],
                )
            )
            AppLogger.log_debug(f"chunks deleted. successful - {result.successful}, failed - {result.failed}")

    async def update_timestamps(
        self,
        chunk_hashes: List[str],
        updated_at: datetime,
        created_at: Optional[datetime] = None,
    ) -> None:
        """
        Efficiently update timestamps for chunk_files without re-inserting full objects.
        Uses Weaviate's async partial update (PATCH) API with concurrency control.
        """
        await self.ensure_collection_connections()

        ts_updates = {"updated_at": updated_at.isoformat()}
        if created_at is not None:
            ts_updates["created_at"] = created_at.isoformat()

        BATCH_SIZE = 500  # noqa: N806
        MAX_CONCURRENCY = 50  # prevent httpcore.PoolTimeout by limiting simultaneous connections  # noqa: N806
        sem = asyncio.Semaphore(MAX_CONCURRENCY)

        async def safe_update(uuid_key: str) -> None:
            """Update a single chunk safely with semaphore + error isolation."""
            async with sem:
                try:
                    await self.async_collection.data.update(
                        uuid=generate_uuid5(uuid_key),
                        properties=ts_updates,
                    )
                except Exception as e:  # noqa: BLE001
                    # Log but continue other updates
                    AppLogger.log_warn(f"⚠️ Failed to update chunk_file {uuid_key}: {e}")

        try:
            for i in range(0, len(chunk_hashes), BATCH_SIZE):
                batch = chunk_hashes[i : i + BATCH_SIZE]
                await asyncio.gather(*(safe_update(ch) for ch in batch))

        except Exception as ex:
            AppLogger.log_error(f"❌ Failed to update timestamps for {len(chunk_hashes)} chunk_files, error: {ex}")
            raise

    async def update_embedding(self, chunk: ChunkInfo) -> None:
        await self.ensure_collection_connections()
        try:
            await self.async_collection.data.update(uuid=generate_uuid5(chunk.content_hash), vector=chunk.embedding)
        except Exception as error:  # noqa: BLE001
            AppLogger.log_error(f"Could not update embedding: {error}")
