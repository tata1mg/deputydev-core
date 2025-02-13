from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple

from services.chunking.chunker.base_chunker import BaseChunker
from services.embedding.base_embedding_manager import BaseEmbeddingManager
from services.repository.dataclasses.main import WeaviateSyncAndAsyncClients
from services.search.dataclasses.main import SearchTypes
from services.search.native.search import NativeSearch
from services.search.vector_db_based.search import VectorDBBasedSearch
from services.chunking.chunk_info import ChunkInfo


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
