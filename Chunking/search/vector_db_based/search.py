from typing import Dict, List, Tuple

from models.chunk_info import ChunkInfo, ChunkSourceDetails
from repository.chunk_service import ChunkService
from repository.chunk_files_service import ChunkFilesService
from repository.chunk_usages_service import ChunkUsagesService
from repository.dataclasses.main import WeaviateSyncAndAsyncClients


class VectorDBBasedSearch:
    @classmethod
    async def perform_search(
            cls,
            whitelisted_file_commits: Dict[str, str],
            query: str,
            query_vector: List[float],
            weaviate_client: WeaviateSyncAndAsyncClients,
            usage_hash: str,
    ) -> Tuple[List[ChunkInfo], int]:

        chunk_files = await ChunkFilesService(weaviate_client).get_chunk_files_by_commit_hashes(
            whitelisted_file_commits
        )
        chunk_hashes = [chunk_file.chunk_hash for chunk_file in chunk_files]

        ChunkUsagesService(weaviate_client).add_chunk_usage(
            chunk_hashes=chunk_hashes,
            usage_hash=usage_hash,
        )

        sorted_chunk_dtos = await ChunkService(weaviate_client).perform_filtered_vector_hybrid_search(
            chunk_hashes=chunk_hashes,
            query=query,
            query_vector=query_vector,
        )

        # merge chunk files and chunk dtos
        chunk_info_list: List[ChunkInfo] = []
        for chunk_dto in sorted_chunk_dtos:
            for chunk_file in chunk_files:
                if chunk_file.chunk_hash == chunk_dto.chunk_hash:
                    chunk_info_list.append(
                        ChunkInfo(
                            content=chunk_dto.text,
                            source_details=ChunkSourceDetails(
                                file_path=chunk_file.file_path,
                                file_hash=chunk_file.file_hash,
                                start_line=chunk_file.start_line,
                                end_line=chunk_file.end_line,
                            ),
                            embedding=None,
                        )
                    )
                    break

        return chunk_info_list, 0
