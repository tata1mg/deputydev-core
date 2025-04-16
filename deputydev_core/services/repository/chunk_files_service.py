import time
from datetime import datetime
from typing import Dict, List, Optional

import weaviate.classes.query as wq
from weaviate.classes.query import Filter
from weaviate.util import generate_uuid5

from deputydev_core.models.dao.weaviate.chunk_files import ChunkFiles
from deputydev_core.models.dto.chunk_file_dto import ChunkFileDTO
from deputydev_core.services.repository.base_weaviate_repository import (
    BaseWeaviateRepository,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.constants.constants import (
    CHUNKFILE_KEYWORD_PROPERTY_MAP,
    PropertyTypes,
)


class ChunkFilesService(BaseWeaviateRepository):
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients):
        super().__init__(weaviate_client, ChunkFiles.collection_name)

    async def get_chunk_files_by_commit_hashes(self, file_to_commit_hashes: Dict[str, str]) -> List[ChunkFileDTO]:
        await self.ensure_collection_connections()
        BATCH_SIZE = 1000
        MAX_RESULTS_PER_QUERY = 10000
        all_chunk_files = []
        try:
            # Convert dictionary items to list for batch processing
            file_commit_pairs = list(file_to_commit_hashes.items())

            # Process in smaller batches
            for i in range(0, len(file_commit_pairs), BATCH_SIZE):
                batch_pairs = file_commit_pairs[i : i + BATCH_SIZE]

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
            AppLogger.log_error("Failed to get chunk files by commit hashes")
            raise ex

    async def get_only_import_chunk_files_by_commit_hashes(self, file_to_commit_hashes: Dict[str, str]) -> List[ChunkFileDTO]:
        await self.ensure_collection_connections()
        BATCH_SIZE = 1000
        MAX_RESULTS_PER_QUERY = 10000
        all_chunk_files = []
        try:
            # Convert dictionary items to list for batch processing
            file_commit_pairs = list(file_to_commit_hashes.items())

            # Process in smaller batches
            for i in range(0, len(file_commit_pairs), BATCH_SIZE):
                batch_pairs = file_commit_pairs[i : i + BATCH_SIZE]

                # Single query per batch without offset pagination
                batch_files = await self.async_collection.query.fetch_objects(
                    filters=Filter.any_of(
                        [
                            Filter.all_of(
                                [
                                    Filter.by_property("file_path").equal(file_path),
                                    Filter.by_property("file_hash").equal(commit_hash),
                                    Filter.by_property("has_imports").equal(True),
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
            AppLogger.log_error("Failed to get chunk files by commit hashes")
            raise ex

    # async def get_file_path_to_chunk_hashes(self, chunk_files: List[ChunkFileDTO]) -> Dict[str, List[str]]:
    #     file_to_hashes = {}
    #     for chunk_file in chunk_files:
    #         file_path = chunk_file.file_path
    #         chunk_hash = chunk_file.chunk_hash
    #         if file_path not in file_to_hashes:
    #             file_to_hashes[file_path] = []
    #         file_to_hashes[file_path].append(chunk_hash)
    #     return file_to_hashes

    async def bulk_insert(self, chunks: List[ChunkFileDTO]) -> None:
        await self.ensure_collection_connections()
        with self.sync_collection.batch.dynamic() as _batch:
            for chunk in chunks:
                chunk_file_uuid = generate_uuid5(
                    f"{chunk.file_path}{chunk.file_hash}{chunk.start_line}{chunk.end_line}"
                )
                chunk = chunk.model_dump(mode="json", exclude={"id"})
                chunk["meta_info"] = {"hierarchy": chunk["meta_info"]["hierarchy"]} if chunk["meta_info"] else None
                _batch.add_object(
                    properties=chunk,
                    uuid=chunk_file_uuid,
                )

    async def cleanup_old_chunk_files(self, last_used_lt: datetime, exclusion_chunk_hashes: List[str]) -> None:
        await self.ensure_collection_connections()
        batch_size = 1000
        while True:
            deletable_objects = self.sync_collection.query.fetch_objects(
                limit=batch_size,
                filters=Filter.all_of(
                    [
                        *[
                            Filter.by_property("chunk_hash").not_equal(chunk_hash)
                            for chunk_hash in exclusion_chunk_hashes
                        ],
                        Filter.by_property("created_at").less_than(last_used_lt),
                    ]
                ),
            )

            AppLogger.log_debug(f"{len(deletable_objects.objects)} chunk_files to be deleted in batch")

            if len(deletable_objects.objects) <= 0:
                break

            result = self.sync_collection.data.delete_many(
                Filter.any_of(
                    [Filter.by_id().equal(obj.uuid) for obj in deletable_objects.objects],
                )
            )
            AppLogger.log_debug(f"chunk_files deleted. successful - {result.successful}, failed - {result.failed}")

    async def get_autocomplete_keyword_chunks(
        self, keyword: str, chunkable_files_and_hashes: Dict[str, str], limit: int = 50
    ) -> List[ChunkFileDTO]:
        """
        Search for code symbols using BM25 and fuzzy matching
        """
        try:
            start_time = time.time()
            await self.ensure_collection_connections()
            file_filters = None
            if chunkable_files_and_hashes and len(chunkable_files_and_hashes) > 0:
                file_filters = Filter.any_of(
                    [
                        Filter.all_of(
                            [
                                Filter.by_property("file_path").equal(file_path),
                                Filter.by_property("file_hash").equal(file_hash),
                            ]
                        )
                        for file_path, file_hash in chunkable_files_and_hashes.items()
                    ]
                )
            if len(keyword) < 3:
                content_filters = Filter.any_of(
                    [
                        Filter.by_property(PropertyTypes.FUNCTION.value).like(f"*{keyword}*"),
                        Filter.by_property(PropertyTypes.CLASS.value).like(f"*{keyword}*"),
                        Filter.by_property(PropertyTypes.FILE.value).like(f"*{keyword}*"),
                        Filter.by_property(PropertyTypes.FILE_NAME.value).like(f"*{keyword}*"),
                    ]
                )
                combined_filter = Filter.all_of([file_filters, content_filters])
                results = await self.async_collection.query.fetch_objects(
                    filters=combined_filter,
                    return_metadata=wq.MetadataQuery(score=True),
                    limit=limit,
                )
            else:
                results = await self.async_collection.query.bm25(
                    query=keyword,
                    query_properties=[
                        PropertyTypes.FUNCTION.value,
                        PropertyTypes.CLASS.value,
                        PropertyTypes.FILE.value,
                        PropertyTypes.FILE_NAME.value,
                    ],
                    filters=file_filters,
                    return_metadata=wq.MetadataQuery(score=True),
                    limit=limit,
                )

            elapsed_time = time.time() - start_time
            AppLogger.log_info(f"Code search completed in {elapsed_time:.4f} seconds")

            return results.objects

        except Exception as ex:
            AppLogger.log_error("Failed to search code symbols")
            raise ex

    async def get_keyword_type_chunks(
        self, keyword: str, type: str, chunkable_files_and_hashes, limit: int = 50
    ) -> List[ChunkFileDTO]:
        """
        Search for code symbols using BM25 and fuzzy matching
        """
        try:
            start_time = time.time()
            await self.ensure_collection_connections()
            file_filters = None
            if chunkable_files_and_hashes and len(chunkable_files_and_hashes) > 0:
                file_filters = Filter.any_of(
                    [
                        Filter.all_of(
                            [
                                Filter.by_property("file_path").equal(file_path),
                                Filter.by_property("file_hash").equal(file_hash),
                            ]
                        )
                        for file_path, file_hash in chunkable_files_and_hashes.items()
                    ]
                )
            if len(keyword) < 3:
                content_filters = Filter.any_of(
                    [
                        Filter.by_property(CHUNKFILE_KEYWORD_PROPERTY_MAP[type][i]).like(f"*{keyword}*")
                        for i in range(len(CHUNKFILE_KEYWORD_PROPERTY_MAP[type]))
                    ]
                )
                combined_filter = Filter.all_of([file_filters, content_filters])
                results = await self.async_collection.query.fetch_objects(
                    filters=combined_filter,
                    return_metadata=wq.MetadataQuery(score=True),
                    limit=limit,
                )
            else:
                results = await self.async_collection.query.bm25(
                    query=keyword,
                    query_properties=CHUNKFILE_KEYWORD_PROPERTY_MAP[type],
                    filters=file_filters,
                    return_metadata=wq.MetadataQuery(score=True),
                    limit=limit,
                )

            elapsed_time = time.time() - start_time
            AppLogger.log_info(f"Code search completed in {elapsed_time:.4f} seconds")

            return results.objects

        except Exception as ex:
            AppLogger.log_error("Failed to search code symbols")
            raise ex

    async def get_chunk_files_matching_exact_search_key_on_file_hash(
        self, search_key: str, search_type: str, file_path: str, file_hash: str
    ) -> List[ChunkFileDTO]:
        file_filter = Filter.all_of(
            [
                Filter.by_property("file_path").equal(file_path),
                Filter.by_property("file_hash").equal(file_hash),
            ]
        )

        search_filter = None
        if search_type == "class":
            search_filter = Filter.by_property(PropertyTypes.CLASS.value).contains_any([search_key])
        elif search_type == "function":
            search_filter = Filter.by_property(PropertyTypes.FUNCTION.value).contains_any([search_key])

        combined_filter = Filter.all_of([file_filter, search_filter] if search_filter else [file_filter])
        results = await self.async_collection.query.fetch_objects(
            filters=combined_filter,
            limit=200,
        )
        all_chunk_file_dtos = [
            ChunkFileDTO(
                **chunk_file_obj.properties,
                id=str(chunk_file_obj.uuid),
            )
            for chunk_file_obj in results.objects
        ]
        sorted_chunk_file_dtos = sorted(
            all_chunk_file_dtos,
            key=lambda x: x.start_line,
        )
        return sorted_chunk_file_dtos

    async def get_import_only_chunk_files_matching_exact_search_key_on_file_hash(
        self, search_key: str, search_type: str, file_path: str, file_hash: str
    ) -> List[ChunkFileDTO]:
        file_filter = Filter.all_of(
            [
                Filter.by_property("file_path").equal(file_path),
                Filter.by_property("file_hash").equal(file_hash),
                Filter.by_property("has_imports").equal(True),
            ]
        )

        search_filter = None
        if search_type == "class":
            search_filter = Filter.by_property(PropertyTypes.CLASS.value).contains_any([search_key])
        elif search_type == "function":
            search_filter = Filter.by_property(PropertyTypes.FUNCTION.value).contains_any([search_key])

        combined_filter = Filter.all_of([file_filter, search_filter] if search_filter else [file_filter])
        results = await self.async_collection.query.fetch_objects(
            filters=combined_filter,
            limit=200,
        )
        all_chunk_file_dtos = [
            ChunkFileDTO(
                **chunk_file_obj.properties,
                id=str(chunk_file_obj.uuid),
            )
            for chunk_file_obj in results.objects
        ]
        sorted_chunk_file_dtos = sorted(
            all_chunk_file_dtos,
            key=lambda x: x.start_line,
        )
        return sorted_chunk_file_dtos
