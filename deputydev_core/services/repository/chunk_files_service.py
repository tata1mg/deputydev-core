import asyncio
from typing import Dict, List
from weaviate.classes.query import Filter
from weaviate.collections.classes.data import DataObject
from deputydev_core.models.dao.weaviate.chunk_files import ChunkFiles
from deputydev_core.models.dto.chunk_file_dto import ChunkFileDTO
from deputydev_core.services.repository.dataclasses.main import WeaviateSyncAndAsyncClients


class ChunkFilesService:
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients):
        self.weaviate_client = weaviate_client
        self.async_collection = weaviate_client.async_client.collections.get(ChunkFiles.collection_name)
        self.sync_collection = weaviate_client.sync_client.collections.get(ChunkFiles.collection_name)

    async def get_chunk_files_by_commit_hashes(self, file_to_commit_hashes: Dict[str, str]) -> List[ChunkFileDTO]:
        BATCH_SIZE = 1000
        MAX_RESULTS_PER_QUERY = 10000
        all_chunk_files = []
        try:
            # Convert dictionary items to list for batch processing
            file_commit_pairs = list(file_to_commit_hashes.items())

            # Process in smaller batches
            for i in range(0, len(file_commit_pairs), BATCH_SIZE):
                batch_pairs = file_commit_pairs[i: i + BATCH_SIZE]

                # Single query per batch without offset pagination
                batch_files = await self.async_collection.query.fetch_objects(
                    filters=Filter.any_of(
                        [
                            Filter.all_of(
                                [
                                    Filter.by_property("file_path").equal(file_path),
                                    Filter.by_property("file_hash").equal(commit_hash),
                                ]
                            )
                            for file_path, commit_hash in batch_pairs
                        ]
                    ),
                    limit=MAX_RESULTS_PER_QUERY,
                )

                # Convert to DTOs efficiently
                if batch_files.objects:
                    batch_dtos = [
                        ChunkFileDTO(
                            **chunk_file_obj.properties,
                            id=str(chunk_file_obj.uuid),
                        )
                        for chunk_file_obj in batch_files.objects
                    ]
                    all_chunk_files.extend(batch_dtos)

            return all_chunk_files

        except Exception as ex:
            raise ex

    async def bulk_insert(self, chunks: List[ChunkFileDTO]) -> None:
        batch_size = 200
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            await self.async_collection.data.insert_many(
                [DataObject(properties=chunk.model_dump(mode="json", exclude={"id"})) for chunk in batch]
            )
            await asyncio.sleep(0.2)  # sleep has been added for controlled insertion

    def cleanup_old_chunk_files(self, chunk_hashes_to_clean: List[str]) -> None:
        batch_size = 500
        for i in range(0, len(chunk_hashes_to_clean), batch_size):
            chunk_hashes_batch = chunk_hashes_to_clean[i: i + batch_size]
            self.sync_collection.data.delete_many(
                Filter.any_of(
                    [Filter.by_property("chunk_hash").equal(chunk_hash) for chunk_hash in chunk_hashes_batch]
                ),
            )
