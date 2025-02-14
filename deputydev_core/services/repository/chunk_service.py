import asyncio
from typing import List, Tuple
from weaviate.classes.query import Filter
from weaviate.collections.classes.data import DataObject
from weaviate.util import generate_uuid5

from deputydev_core.models.dao.weaviate.chunks import Chunks
from deputydev_core.models.dto.chunk_dto import ChunkDTO, ChunkDTOWithVector
from deputydev_core.services.repository.dataclasses.main import WeaviateSyncAndAsyncClients


class ChunkService:
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients):
        self.weaviate_client = weaviate_client
        self.async_collection = weaviate_client.async_client.collections.get(Chunks.collection_name)
        self.sync_collection = weaviate_client.sync_client.collections.get(Chunks.collection_name)

    async def perform_filtered_vector_hybrid_search(
            self, chunk_hashes: List[str], query: str, query_vector: List[float], limit: int = 20, alpha: float = 0.7
    ) -> List[ChunkDTO]:
        try:
            all_chunks = await self.async_collection.query.hybrid(
                filters=Filter.by_property("chunk_hash").contains_any(chunk_hashes),
                query=query,
                limit=limit,
                vector=query_vector,
                alpha=alpha,
            )
            return [
                ChunkDTO(
                    **chunk_file_obj.properties,
                    id=str(chunk_file_obj.uuid),
                )
                for chunk_file_obj in all_chunks.objects
            ]
        except Exception as ex:
            raise ex

    async def get_chunks_by_chunk_hashes(self, chunk_hashes: List[str]) -> List[Tuple[ChunkDTO, List[float]]]:
        BATCH_SIZE = 10000
        all_chunks = []
        MAX_RESULTS_PER_QUERY = 10000
        try:
            # Process chunk hashes in batches
            for i in range(0, len(chunk_hashes), BATCH_SIZE):
                batch_hashes = chunk_hashes[i: i + BATCH_SIZE]
                batch_chunks = await self.async_collection.query.fetch_objects(
                    filters=Filter.any_of(
                        [Filter.by_property("chunk_hash").equal(chunk_hash) for chunk_hash in batch_hashes]
                    ),
                    limit=MAX_RESULTS_PER_QUERY,
                )
                # Break if no more results
                if batch_chunks.objects:
                    # Convert to DTOs efficiently using list comprehension
                    batch_dtos = [
                        (ChunkDTO(**chunk_obj.properties, id=str(chunk_obj.uuid)), chunk_obj.vector["default"])
                        for chunk_obj in batch_chunks.objects
                    ]
                    all_chunks.extend(batch_dtos)

            return all_chunks

        except Exception as ex:
            raise

    async def bulk_insert(self, chunks: List[ChunkDTOWithVector]) -> None:
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            await self.async_collection.data.insert_many(
                [
                    DataObject(
                        properties=chunk.dto.model_dump(mode="json", exclude={"id"}),
                        vector=chunk.vector,
                        uuid=generate_uuid5(chunk.dto.chunk_hash),
                    )
                    for chunk in batch
                ]
            )
            await asyncio.sleep(0.2)

    def cleanup_old_chunks(self, chunk_hashes_to_clean: List[str]) -> None:
        batch_size = 500
        for i in range(0, len(chunk_hashes_to_clean), batch_size):
            batch = chunk_hashes_to_clean[i: i + batch_size]
            self.sync_collection.data.delete_many(
                Filter.all_of([Filter.by_id().not_equal(generate_uuid5(chunk_hash)) for chunk_hash in batch])
            )
