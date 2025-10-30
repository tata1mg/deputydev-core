from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple

from deputydev_core.services.chunking.chunk_info import ChunkInfo


class BaseChunkReranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        relevant_chunks: List[ChunkInfo],
        focus_chunks: Optional[List[ChunkInfo]] = None,
        is_llm_reranking_enabled: bool = False,
        one_dev_client: Optional[Any] = None,
        auth_token_key: Optional[str] = None,
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
