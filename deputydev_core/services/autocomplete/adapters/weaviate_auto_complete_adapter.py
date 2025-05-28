from typing import Any, List

import weaviate.classes.query as wq
from weaviate.classes.query import Filter

from deputydev_core.models.dao.weaviate.chunk_files import ChunkFiles
from deputydev_core.models.dto.chunk_file_dto import ChunkFileDTO
from deputydev_core.services.autocomplete.autocomplete_service_async import (
    AutoCompleteServiceAsync,
)
from deputydev_core.services.autocomplete.dataclasses.main import (
    AutoCompleteSearch,
    SearchPath,
)
from deputydev_core.services.repository.base_weaviate_repository import (
    BaseWeaviateRepository,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.utils.config_manager import ConfigManager
from deputydev_core.utils.constants.constants import CHUNKFILE_KEYWORD_PROPERTY_MAP


class WeaviateAutocompleteAdapter(AutoCompleteServiceAsync, BaseWeaviateRepository):
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients):
        super().__init__(weaviate_client, ChunkFiles.collection_name)

    async def _build_filters(self, search_paths: List[SearchPath]) -> Any:
        file_filters = []
        if search_paths and len(search_paths) > 0:
            file_filters = Filter.any_of(
                [
                    Filter.all_of(
                        [
                            Filter.by_property("file_path").equal(
                                search_path.file_path
                            ),
                            Filter.by_property("file_hash").equal(
                                search_path.file_hash
                            ),
                        ]
                    )
                    for search_path in search_paths
                ]
            )
        return file_filters

    async def _fuzzy_search(self, request: AutoCompleteSearch) -> List[ChunkFileDTO]:
        await self.ensure_collection_connections()
        assert len(request.keyword) > 0
        # keywords having search
        apply_pre_filter = (
            len(request.search_paths)
            < ConfigManager.configs["AUTOCOMPLETE_SEARCH"]["PRE_FILTER_LIMIT"]
        )
        if apply_pre_filter:
            filters = await self._build_filters(request.search_paths)
        else:
            request.limit = (
                request.limit * 10
            )  # expected no of repos = 10 in users system
            filters = []

        if len(request.keyword) < 3:
            content_filters = Filter.any_of(
                [
                    Filter.by_property(CHUNKFILE_KEYWORD_PROPERTY_MAP[type][i]).like(
                        f"*{request.keyword}*"
                    )
                    for type in CHUNKFILE_KEYWORD_PROPERTY_MAP
                    for i in range(len(CHUNKFILE_KEYWORD_PROPERTY_MAP[type]))
                ]
            )
            combined_filter = (
                Filter.all_of([filters, content_filters])
                if filters
                else content_filters
            )
            results = await self.async_collection.query.fetch_objects(
                filters=combined_filter,
                return_metadata=wq.MetadataQuery(score=True),
                limit=request.limit,
            )
        else:
            results = await self.async_collection.query.bm25(
                query=request.keyword,
                query_properties=[
                    CHUNKFILE_KEYWORD_PROPERTY_MAP[typ][i]
                    for typ in CHUNKFILE_KEYWORD_PROPERTY_MAP
                    for i in range(len(CHUNKFILE_KEYWORD_PROPERTY_MAP[typ]))
                ],
                filters=filters or None,
                return_metadata=wq.MetadataQuery(score=True),
                limit=request.limit,
            )
        records = results.objects
        final_records: List[ChunkFileDTO] = []
        if not apply_pre_filter:
            file_path_hash_map = {
                paths.file_path: paths.file_hash for paths in request.search_paths
            }
            for record in records:
                if (
                    record.properties["file_path"] in file_path_hash_map
                    and file_path_hash_map[record.properties["file_path"]]
                    == record.properties["file_hash"]
                ):
                    final_records.append(record)
        else:
            final_records = records
        return final_records
