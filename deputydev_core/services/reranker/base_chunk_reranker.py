from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

from deputydev_core.services.chunking.chunk_info import ChunkInfo


class BaseChunkReranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        focus_chunks: List[ChunkInfo],
        relevant_chunks: List[ChunkInfo],
        query: str,
        is_llm_reranking_enabled: bool,
    ) -> Tuple[List[ChunkInfo], Optional[int]]:
        """
        Reranks the focus chunks based on the related codebase chunks.

        Args:
            focus_chunks (List[ChunkInfo]): The focus chunks to be reranked.
            relevant_chunks (List[ChunkInfo]): The related codebase chunks.
            query (str): The query on which the chunks are to be reranked.
            is_llm_reranking_enabled(bool): Whether or not reranker is enabled

        Returns:
            List[ChunkInfo]: The reranked focus chunks.
        """
        raise NotImplementedError("Rerank method must be implemented in the child class")
