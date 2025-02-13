from concurrent.futures import ProcessPoolExecutor
from typing import List, Tuple

from services.chunking.chunker.base_chunker import BaseChunker
from services.chunking.document import chunks_to_docs
from services.embedding.base_embedding_manager import BaseEmbeddingManager
from services.search.native.lexical_search import lexical_search
from services.chunking.chunk_info import ChunkInfo
from services.search.native.vector_search import compute_vector_search_scores


class NativeSearch:
    @classmethod
    async def perform_search(
            cls,
            query: str,
            embedding_manager: BaseEmbeddingManager,
            chunking_handler: BaseChunker,
            process_executor: ProcessPoolExecutor,
            max_chunks_to_return: int,
    ) -> Tuple[List[ChunkInfo], int]:
        """
        Perform a search operation on documents and document chunks.

        Args:
            all_docs (List[Document]): List of all documents.
            all_chunks (List[ChunkInfo]): List of all document chunks.
            query (Query): Search query.

        Returns:
            Dict[int, float]: Search results containing scores for each document chunk.
        """
        all_chunks = await chunking_handler.create_chunks_and_docs()
        all_docs = chunks_to_docs(all_chunks)

        # Perform lexical search
        content_to_lexical_score_list = await lexical_search(query, all_docs, process_executor)
        # Compute vector search scores asynchronously
        files_to_scores_list, input_tokens = await compute_vector_search_scores(
            query, all_chunks, embedding_manager, process_executor=process_executor
        )
        # Calculate scores for each chunk
        for chunk in all_chunks:
            # Default values for scores
            vector_score = files_to_scores_list.get(chunk.denotation, 0.04)
            chunk_score = 0.02

            # Adjust chunk score if denotation is found in lexical search results
            if chunk.denotation in content_to_lexical_score_list:
                chunk_score = content_to_lexical_score_list[chunk.denotation] + (vector_score * 3.5)
                content_to_lexical_score_list[chunk.denotation] = chunk_score
            else:
                # If denotation not found, calculate score based on vector search only
                content_to_lexical_score_list[chunk.denotation] = chunk_score * vector_score
        # Return search results

        ranked_snippets_list = sorted(
            all_chunks,
            key=lambda chunk: content_to_lexical_score_list[chunk.denotation],
            reverse=True,
        )[0:max_chunks_to_return]

        return ranked_snippets_list, input_tokens
