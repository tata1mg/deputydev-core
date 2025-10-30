from typing import Any, List, Optional, Tuple

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.reranker.base_chunk_reranker import BaseChunkReranker
from deputydev_core.utils.chunk_utils import filter_chunks_by_denotation, jsonify_chunks
from deputydev_core.utils.config_manager import ConfigManager
from deputydev_core.utils.context_value import ContextValue


class RerankerService(BaseChunkReranker):
    def __init__(self, session_id: Optional[int] = None, session_type: Optional[str] = None) -> None:
        self.session_id = session_id
        self.session_type = session_type

    async def rerank(
        self,
        query: str,
        relevant_chunks: List[ChunkInfo],
        is_llm_reranking_enabled: bool,
        one_dev_client: Any,
        auth_token_key: str,
        focus_chunks: Optional[List[ChunkInfo]] = None,
    ) -> Tuple[List[ChunkInfo], Optional[int]]:
        payload = {
            "query": query,
            "relevant_chunks": jsonify_chunks(relevant_chunks),
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ContextValue.get(auth_token_key)}",
        }
        if self.session_id:
            headers["X-Session-Id"] = str(self.session_id)

        if self.session_type:
            headers["X-Session-Type"] = self.session_type
        data = await one_dev_client.llm_reranking(payload, headers=headers)
        filtered_and_ranked_chunks_denotations = data.get("reranked_denotations") if data else None
        returned_session_id = data["session_id"]

        if not filtered_and_ranked_chunks_denotations:
            return relevant_chunks, returned_session_id

        return (
            filter_chunks_by_denotation(
                relevant_chunks,
                filtered_and_ranked_chunks_denotations,
            ),
            returned_session_id,
        )

    @classmethod
    def get_default_chunks(
        cls, focus_chunks: List[ChunkInfo], related_codebase_chunks: List[ChunkInfo]
    ) -> List[ChunkInfo]:
        max_default_chunks_to_return = ConfigManager.config["CHUNKING"]["DEFAULT_MAX_CHUNKS_CODE_GENERATION"]
        chunks = focus_chunks + related_codebase_chunks
        chunks.sort(key=lambda chunk: chunk.search_score, reverse=True)
        return chunks[:max_default_chunks_to_return]
