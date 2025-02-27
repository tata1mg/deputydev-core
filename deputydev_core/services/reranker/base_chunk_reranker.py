from abc import ABC, abstractmethod
from typing import List

from deputydev_core.services.chunking.chunk_info import ChunkInfo


class BaseChunkReranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        focus_chunks: List[ChunkInfo],
        related_codebase_chunks: List[ChunkInfo],
        query: str,
    ) -> List[ChunkInfo]:
        """
        Reranks the focus chunks based on the related codebase chunks.

        Args:
            focus_chunks (List[ChunkInfo]): The focus chunks to be reranked.
            related_codebase_chunks (List[ChunkInfo]): The related codebase chunks.
            query (str): The query on which the chunks are to be reranked.

        Returns:
            List[ChunkInfo]: The reranked focus chunks.
        """
        raise NotImplementedError("Rerank method must be implemented in the child class")
