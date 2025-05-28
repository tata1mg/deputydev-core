from typing import Dict, List, Tuple

from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails
from deputydev_core.services.repository.chunk_files_service import ChunkFilesService
from deputydev_core.services.repository.chunk_service import ChunkService
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)


class VectorDBBasedSearch:
    @classmethod
    async def perform_search(
        cls,
        whitelisted_file_commits: Dict[str, str],
        query: str,
        query_vector: List[float],
        weaviate_client: WeaviateSyncAndAsyncClients,
        max_chunks_to_return: int,
    ) -> Tuple[List[ChunkInfo], int]:
        chunk_files = await ChunkFilesService(weaviate_client).get_chunk_files_by_commit_hashes(
            whitelisted_file_commits
        )
        chunk_hashes = [chunk_file.chunk_hash for chunk_file in chunk_files]

        sorted_chunk_dtos = await ChunkService(weaviate_client).perform_filtered_vector_hybrid_search(
            chunk_hashes=chunk_hashes,
            query=query,
            query_vector=query_vector,
            limit=max_chunks_to_return,
        )

        # merge chunk files and chunk dtos
        chunk_info_list: List[ChunkInfo] = []
        for chunk_dto in sorted_chunk_dtos:
            for chunk_file in chunk_files:
                if chunk_file.chunk_hash == chunk_dto.chunk.chunk_hash:
                    chunk_info_list.append(
                        ChunkInfo(
                            content=chunk_dto.chunk.text,
                            source_details=ChunkSourceDetails(
                                file_path=chunk_file.file_path,
                                file_hash=chunk_file.file_hash,
                                start_line=chunk_file.start_line,
                                end_line=chunk_file.end_line,
                            ),
                            embedding=None,
                            search_score=chunk_dto.score,
                            metadata=chunk_file.meta_info,
                        )
                    )
                    break

        new_file_path_to_hash_map_for_import_only: Dict[str, str] = {
            chunk_info.source_details.file_path: chunk_info.source_details.file_hash for chunk_info in chunk_info_list
        }

        import_only_chunk_files = await ChunkFilesService(weaviate_client).get_only_import_chunk_files_by_commit_hashes(
            file_to_commit_hashes=new_file_path_to_hash_map_for_import_only
        )

        import_only_chunk_hashes = [chunk_file.chunk_hash for chunk_file in import_only_chunk_files]

        import_only_chunk_dtos = await ChunkService(weaviate_client).get_chunks_by_chunk_hashes(
            chunk_hashes=import_only_chunk_hashes,
        )

        chunk_info_set = set(chunk_info_list)

        for chunk_dto, _vector in import_only_chunk_dtos:
            for chunk_file in import_only_chunk_files:
                if chunk_file.chunk_hash == chunk_dto.chunk_hash:
                    chunk_info_set.add(
                        ChunkInfo(
                            content=chunk_dto.text,
                            source_details=ChunkSourceDetails(
                                file_path=chunk_file.file_path,
                                file_hash=chunk_file.file_hash,
                                start_line=chunk_file.start_line,
                                end_line=chunk_file.end_line,
                            ),
                            embedding=None,
                            metadata=chunk_file.meta_info,
                        )
                    )
                    break

        updated_chunk_info_list = list(chunk_info_set)

        updated_chunk_info_list.sort(key=lambda x: (x.source_details.file_path, x.source_details.start_line))

        return updated_chunk_info_list, 0
