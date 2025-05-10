import copy
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple

from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails
from deputydev_core.services.chunking.chunker.base_chunker import BaseChunker
from deputydev_core.services.embedding.base_embedding_manager import (
    BaseEmbeddingManager,
)
from deputydev_core.services.repo.local_repo.base_local_repo_service import (
    BaseLocalRepo,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.services.reranker.base_chunk_reranker import BaseChunkReranker
from deputydev_core.services.search.dataclasses.main import SearchTypes
from deputydev_core.services.search.search import perform_search
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.file_utils import read_file


class ChunkingManger:
    @classmethod
    def build_focus_query(cls, user_query: str, custom_context_code_chunks: List[ChunkInfo]):
        if not custom_context_code_chunks:
            return user_query

        focus_query = f"{user_query}"
        for chunk in custom_context_code_chunks:
            focus_query += f"\n{chunk.content}"
        return focus_query

    @classmethod
    async def get_relevant_context_from_focus_files(
        cls,
        focus_file_paths: List[str],
        user_query: str,
        custom_context_code_chunks: List[ChunkInfo],
        chunkable_files_with_hashes: Dict[str, str],
        embedding_manager: BaseEmbeddingManager,
        process_executor: ProcessPoolExecutor,
        max_chunks_to_return: int,
        query_vector: Optional[List[float]] = None,
        search_type: SearchTypes = SearchTypes.VECTOR_DB_BASED,
        weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
        chunking_handler: Optional[BaseChunker] = None,
    ):
        filtered_files = {
            file_path: chunkable_files_with_hashes[file_path]
            for file_path in focus_file_paths
            if file_path in chunkable_files_with_hashes
        }

        sorted_chunks, _ = await perform_search(
            query=cls.build_focus_query(user_query, custom_context_code_chunks),
            search_type=search_type,
            embedding_manager=embedding_manager,
            process_executor=process_executor,
            chunkable_files_with_hashes=filtered_files,
            query_vector=query_vector,
            weaviate_client=weaviate_client,
            chunking_handler=chunking_handler,
            max_chunks_to_return=max_chunks_to_return,
        )
        return custom_context_code_chunks + sorted_chunks

    @classmethod
    async def get_relevant_context_from_focus_snippets(
        cls, focus_code_chunks: List[str], local_repo: BaseLocalRepo
    ) -> List[ChunkInfo]:
        custom_context_chunks: List[ChunkInfo] = []
        for focus_code_chunk in focus_code_chunks:
            filepath, lines = focus_code_chunk.split(":")
            lines = lines.split("-")
            abs_filepath = os.path.join(local_repo.repo_path, filepath)
            file_content = read_file(abs_filepath)
            custom_context_chunks.append(
                ChunkInfo(
                    content=file_content,
                    source_details=ChunkSourceDetails(
                        file_path=filepath,
                        file_hash="",
                        start_line=int(lines[0]),
                        end_line=int(lines[1]),
                    ),
                )
            )
        return custom_context_chunks

    @classmethod
    async def get_focus_chunk(
        cls,
        query: str,
        local_repo: BaseLocalRepo,
        custom_context_files: List[str],
        custom_context_code_chunks: List[str],
        chunkable_files_with_hashes: Dict[str, str],
        embedding_manager: BaseEmbeddingManager,
        process_executor: ProcessPoolExecutor,
        max_chunks_to_return: int,
        query_vector: Optional[List[float]] = None,
        search_type: SearchTypes = SearchTypes.VECTOR_DB_BASED,
        weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
        chunking_handler: Optional[BaseChunker] = None,
    ) -> List[ChunkInfo]:
        user_defined_chunks = []
        if custom_context_code_chunks:
            user_defined_chunks = await cls.get_relevant_context_from_focus_snippets(
                custom_context_code_chunks, local_repo
            )
        if custom_context_files:
            return await cls.get_relevant_context_from_focus_files(
                custom_context_files,
                query,
                user_defined_chunks,
                chunkable_files_with_hashes,
                embedding_manager,
                process_executor,
                max_chunks_to_return,
                query_vector,
                search_type=search_type,
                weaviate_client=weaviate_client,
                chunking_handler=chunking_handler,
            )
        else:
            return user_defined_chunks

    @classmethod
    async def get_related_chunk_from_codebase_repo(
        cls,
        query: str,
        focus_chunks: List[ChunkInfo],
        chunkable_files_with_hashes: Dict[str, str],
        embedding_manager: BaseEmbeddingManager,
        process_executor: ProcessPoolExecutor,
        max_chunks_to_return: int,
        query_vector: Optional[List[float]] = None,
        search_type: SearchTypes = SearchTypes.VECTOR_DB_BASED,
        weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
        chunking_handler: Optional[BaseChunker] = None,
    ) -> Tuple[List[ChunkInfo], int]:
        AppLogger.log_info("Completed chunk creation")
        if focus_chunks:
            query = cls.build_focus_query(query, focus_chunks)

        sorted_chunks, input_tokens = await perform_search(
            query=query,
            query_vector=query_vector,
            chunkable_files_with_hashes=chunkable_files_with_hashes,
            search_type=search_type,
            chunking_handler=chunking_handler,
            embedding_manager=embedding_manager,
            process_executor=process_executor,
            weaviate_client=weaviate_client,
            max_chunks_to_return=max_chunks_to_return,
        )
        return sorted_chunks, input_tokens

    @classmethod
    async def get_relevant_chunks(
        cls,
        query: str,
        chunkable_files_with_hashes: Dict[str, str],
        local_repo: BaseLocalRepo,
        embedding_manager: BaseEmbeddingManager,
        process_executor: ProcessPoolExecutor,
        max_chunks_to_return: int,
        focus_files: List[str] = [],
        focus_chunks: List[str] = [],
        focus_directories: List[str] = [],
        query_vector: Optional[List[float]] = None,
        only_focus_code_chunks: bool = False,
        search_type: SearchTypes = SearchTypes.VECTOR_DB_BASED,
        weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
        chunking_handler: Optional[BaseChunker] = None,
        reranker: Optional[BaseChunkReranker] = None,
    ) -> Tuple[list[ChunkInfo], int, list[ChunkInfo]]:
        # Get all chunks from the repository
        focus_chunks_details = await cls.get_focus_chunk(
            query,
            local_repo,
            focus_files,
            focus_chunks,
            chunkable_files_with_hashes,
            embedding_manager,
            process_executor,
            max_chunks_to_return,
            query_vector,
            search_type=search_type,
            weaviate_client=weaviate_client,
            chunking_handler=chunking_handler,
        )
        if only_focus_code_chunks and focus_chunks_details:
            return focus_chunks_details, 0, ""

        if focus_directories:
            focus_files.extend(
                cls.get_focus_files_from_focus_directories(chunkable_files_with_hashes, focus_directories)
            )

        if focus_files:
            # remove focus file to get chunks which are not related to focus chunks
            chunkable_files_with_hashes = copy.deepcopy(chunkable_files_with_hashes)
            for file_path in focus_files:
                del chunkable_files_with_hashes[file_path]

        relevant_chunks, input_tokens = await cls.get_related_chunk_from_codebase_repo(
            query,
            focus_chunks_details,
            chunkable_files_with_hashes,
            embedding_manager,
            process_executor,
            max_chunks_to_return,
            query_vector=query_vector,
            search_type=search_type,
            weaviate_client=weaviate_client,
            chunking_handler=chunking_handler,
        )
        reranked_chunks = await cls.rerank_related_chunks(query, relevant_chunks, reranker, focus_chunks_details)
        return reranked_chunks, input_tokens, focus_chunks_details

    @classmethod
    def get_focus_files_from_focus_directories(cls, chunkable_files_with_hashes, focus_directories):
        focus_files = set()

        for directory in focus_directories:
            for file_path in chunkable_files_with_hashes:
                if file_path.startswith(directory):
                    focus_files.add(file_path)

        return list(focus_files)

    @classmethod
    def exclude_focused_chunks(cls, related_chunk, focus_chunks_details):
        related_chunk = [
            chunk for chunk in related_chunk if chunk.content not in [chunk.content for chunk in focus_chunks_details]
        ]
        return related_chunk

    @classmethod
    async def rerank_related_chunks(cls, query, related_chunks, reranker, focus_chunks_details):
        related_chunks = cls.exclude_focused_chunks(related_chunks, focus_chunks_details)
        if reranker:
            related_chunks = await reranker.rerank(focus_chunks_details, related_chunks, query)
        return related_chunks
