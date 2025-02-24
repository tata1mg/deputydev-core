from datetime import datetime
from typing import List, Tuple

from weaviate.classes.query import Filter, MetadataQuery
from weaviate.util import generate_uuid5

from deputydev_core.models.dao.weaviate.chunks import Chunks
from deputydev_core.models.dto.chunk_dto import (
    ChunkDTO,
    ChunkDTOWithScore,
    ChunkDTOWithVector,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.utils.app_logger import AppLogger


class ChunkService:
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients):
        self.weaviate_client = weaviate_client
        self.async_collection = weaviate_client.async_client.collections.get(
            Chunks.collection_name
        )
        self.sync_collection = weaviate_client.sync_client.collections.get(
            Chunks.collection_name
        )

    async def perform_filtered_vector_hybrid_search(
        self,
        chunk_hashes: List[str],
        query: str,
        query_vector: List[float],
        limit: int = 20,
        alpha: float = 0.7,
    ) -> List[ChunkDTOWithScore]:
        try:
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
        self, chunk_hashes: List[str]
    ) -> List[Tuple[ChunkDTO, List[float]]]:
        BATCH_SIZE = 1000
        all_chunks: List[Tuple[ChunkDTO, List[float]]] = []
        MAX_RESULTS_PER_QUERY = 10000
        try:
            # Process chunk hashes in batches
            for i in range(0, len(chunk_hashes), BATCH_SIZE):
                batch_hashes = chunk_hashes[i : i + BATCH_SIZE]
                batch_chunks = await self.async_collection.query.fetch_objects(
                    filters=Filter.any_of(
                        [
                            Filter.by_id().equal(generate_uuid5(chunk_hash))
                            for chunk_hash in batch_hashes
                        ]
                    ),
                    include_vector=True,
                    limit=MAX_RESULTS_PER_QUERY,
                )
                # Break if no more results
                if batch_chunks.objects:
                    # Convert to DTOs efficiently using list comprehension
                    batch_dtos = [
                        (
                            ChunkDTO(**chunk_obj.properties, id=str(chunk_obj.uuid)),
                            chunk_obj.vector["default"],
                        )
                        for chunk_obj in batch_chunks.objects
                    ]
                    all_chunks.extend(batch_dtos)

            return all_chunks

        except Exception as ex:
            AppLogger.log_error(
                "Failed to get chunk files by commit hashes",
                extra={"chunk_hashes_count": len(chunk_hashes), "error": str(ex)},
            )
            raise

    async def bulk_insert(self, chunks: List[ChunkDTOWithVector]) -> None:
        with self.sync_collection.batch.dynamic() as _batch:
            for chunk in chunks:
                _batch.add_object(
                    properties=chunk.dto.model_dump(mode="json", exclude={"id"}),
                    vector=chunk.vector,
                    uuid=generate_uuid5(chunk.dto.chunk_hash),
                )

    def cleanup_old_chunks(
        self, last_used_lt: datetime, exclusion_chunk_hashes: List[str]
    ) -> None:
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

            AppLogger.log_debug(
                f"{len(deletable_objects.objects)} chunks to be deleted in batch"
            )

            if len(deletable_objects.objects) <= 0:
                break

            result = self.sync_collection.data.delete_many(
                Filter.any_of(
                    [
                        Filter.by_id().equal(obj.uuid)
                        for obj in deletable_objects.objects
                    ],
                )
            )
            AppLogger.log_debug(
                f"chunks deleted. successful - {result.successful}, failed - {result.failed}"
            )
