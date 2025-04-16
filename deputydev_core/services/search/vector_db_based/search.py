from typing import Dict, List, Set, Tuple

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

        # Get import-only chunk files from Weaviate
        # This retrieves all chunk files that have imports
        import_only_chunk_files = await ChunkFilesService(weaviate_client).get_only_import_chunk_files_by_commit_hashes(
            whitelisted_file_commits
        )

        # Extract chunk hashes from import-only chunk files
        # This creates a list of chunk hashes that have imports
        import_only_chunk_hashes = [chunk_file.chunk_hash for chunk_file in import_only_chunk_files]

        # Perform vector search on import-only chunks
        # This retrieves the most relevant import-only chunks based on the query
        import_only_chunk_dtos = await ChunkService(weaviate_client).perform_filtered_vector_hybrid_search(
            chunk_hashes=import_only_chunk_hashes,
            query=query,
            query_vector=query_vector,
            limit=max_chunks_to_return,
        )

        # Create mapping of file paths to their import-only chunk infos
        # This creates a dictionary where each file path maps to a set of ChunkInfo objects
        # that contain import-related content
        import_only_file_path_to_chunk_info: Dict[str, Set[ChunkInfo]] = {}
        for chunk_dto in import_only_chunk_dtos:
            for chunk_file in import_only_chunk_files:
                if chunk_file.chunk_hash == chunk_dto.chunk.chunk_hash:
                    file_path = chunk_file.file_path
                    if file_path not in import_only_file_path_to_chunk_info:
                        import_only_file_path_to_chunk_info[file_path] = set()

                    # Create ChunkInfo for import-only chunk
                    import_only_file_path_to_chunk_info[file_path].add(
                        ChunkInfo(
                            content=chunk_dto.chunk.text,
                            source_details=ChunkSourceDetails(
                                file_path=file_path,
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

        # Merge existing chunk infos with import-only chunk infos
        # This adds the original chunk infos to the sets where they share the same file path
        for chunk_info in chunk_info_list:
            file_path = chunk_info.source_details.file_path
            if file_path in import_only_file_path_to_chunk_info:
                import_only_file_path_to_chunk_info[file_path].add(chunk_info)

        # Create final updated chunk info list
        # This combines all chunk infos (both original and import-only) while maintaining file path grouping
        updated_chunk_info_list: List[ChunkInfo] = []
        for chunk_infos in import_only_file_path_to_chunk_info.values():
            updated_chunk_info_list.extend(list(chunk_infos))

        return updated_chunk_info_list, 0
