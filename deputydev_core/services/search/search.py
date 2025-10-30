from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.chunker.base_chunker import BaseChunker
from deputydev_core.services.embedding.base_embedding_manager import (
    BaseEmbeddingManager,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.services.search.dataclasses.main import SearchTypes
from deputydev_core.services.search.native.search import NativeSearch
from deputydev_core.services.search.vector_db_based.search import VectorDBBasedSearch


async def perform_search(
    query: str,
    chunkable_files_with_hashes: Dict[str, str],
    search_type: SearchTypes,
    embedding_manager: BaseEmbeddingManager,
    process_executor: ProcessPoolExecutor,
    max_chunks_to_return: int,
    chunking_handler: Optional[BaseChunker] = None,
    query_vector: Optional[List[float]] = None,
    weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
) -> Tuple[List[ChunkInfo], int]:
    sorted_chunks: List[ChunkInfo] = []
    input_tokens: int = 0
    if search_type == SearchTypes.NATIVE:
        if not chunking_handler:
            raise ValueError("Chunking handler is required for native search")
        sorted_chunks, input_tokens = await NativeSearch.perform_search(
            query=query,
            embedding_manager=embedding_manager,
            process_executor=process_executor,
            chunking_handler=chunking_handler,
            max_chunks_to_return=max_chunks_to_return,
        )
    elif search_type == SearchTypes.VECTOR_DB_BASED:
        if not weaviate_client:
            raise ValueError("Weaviate client is required for vector db based search")
        if query_vector is None:
            raise ValueError("Query vector is required for vector db based search")
        if not chunkable_files_with_hashes:
            raise ValueError("Chunkable files with hashes are required for vector db based search")
        sorted_chunks, input_tokens = await VectorDBBasedSearch.perform_search(
            whitelisted_file_commits=chunkable_files_with_hashes,
            query=query,
            query_vector=query_vector,
            weaviate_client=weaviate_client,
            max_chunks_to_return=max_chunks_to_return,
        )

    return sorted_chunks, input_tokens


async def perform_semantic_search(
    query: str,
    whitelisted_file_commits: Dict[str, str],
    max_chunks_to_return: int,
    query_vector: List[float],
    weaviate_client: WeaviateSyncAndAsyncClients,
) -> List[ChunkInfo]:
    sorted_chunks: List[ChunkInfo] = []
    sorted_chunks, _ = await VectorDBBasedSearch.perform_search(
        whitelisted_file_commits=whitelisted_file_commits,
        query=query,
        query_vector=query_vector,
        weaviate_client=weaviate_client,
        max_chunks_to_return=max_chunks_to_return,
        include_import_only_chunks=False,
    )

    return sorted_chunks
