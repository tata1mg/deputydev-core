from pathlib import Path
from typing import Any, Dict, Optional

from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
from deputydev_core.services.embedding.base_embedding_manager import BaseEmbeddingManager
from deputydev_core.services.repo.local_repo.local_repo_factory import LocalRepoFactory
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.services.reranker.handlers.llm_reranker import RerankerService
from deputydev_core.services.search.search import perform_semantic_search
from deputydev_core.services.tools.semantic_search.dataclass.main import SemanticSearchParams
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.chunk_utils import jsonify_chunks
from deputydev_core.utils.config_manager import ConfigManager


class SemanticSearch:
    def __init__(
        self, repo_path: str, ripgrep_path: Optional[str], weaviate_client: WeaviateSyncAndAsyncClients
    ) -> None:
        self.repo_path = Path(repo_path)
        self.ripgrep_path = ripgrep_path
        self.weaviate_client = weaviate_client

    async def get_relevant_chunks(
        self,
        params: SemanticSearchParams,
        dev_client: OneDevClient,
        embedding_manager: BaseEmbeddingManager,
        auth_token_key: str,
    ) -> Dict[str, Any]:
        """Retrieve and rerank the most relevant chunks for a given semantic search query."""

        # --- Step 1: Initialize and validate ---
        local_repo = LocalRepoFactory.get_local_repo(params.repo_path, ripgrep_path=self.ripgrep_path)

        # Fetch list of files eligible for chunking and their commit hashes
        chunkable_files = await local_repo.get_chunkable_files_and_commit_hashes()

        # Generate embedding vector for the query
        query_vector = await embedding_manager.embed_text_array(texts=[params.query], store_embeddings=False)
        if (
            len(query_vector) == 0
            or query_vector[0] is None
            or (hasattr(query_vector[0], "size") and query_vector[0].size == 0)
        ):
            raise ValueError("Could not generate embedding vector for the search query.")

        # --- Step 2: Filter files if focus directories are provided ---
        if params.focus_directories:
            filtered_files = {
                path: hash_value
                for path, hash_value in chunkable_files.items()
                if any(str(path).startswith(fd) for fd in params.focus_directories)
            }
        else:
            filtered_files = chunkable_files

        if not filtered_files:
            AppLogger.log_info("No files found after applying focus directory filters.")
            return {
                "relevant_chunks": [],
                "session_id": None,
            }
        # --- Step 3: Retrieve relevant chunks using embeddings ---
        max_chunks = ConfigManager.configs["CHUNKING"]["NUMBER_OF_CHUNKS"]

        relevant_chunks = await perform_semantic_search(
            query=params.query,
            max_chunks_to_return=max_chunks,
            weaviate_client=self.weaviate_client,
            whitelisted_file_commits=filtered_files,
            query_vector=query_vector[0][0],
        )

        # --- Step 4: Rerank results (optionally with LLM-based reranker) ---
        reranker = RerankerService(
            session_id=params.session_id,
            session_type=params.session_type,
        )

        reranked_chunks, session_id = await reranker.rerank(
            query=params.explanation,
            relevant_chunks=relevant_chunks,
            is_llm_reranking_enabled=ConfigManager.configs["CHUNKING"]["IS_LLM_RERANKING_ENABLED"],
            one_dev_client=dev_client,
            auth_token_key=auth_token_key,
        )

        # --- Step 5: Return results in a structured format ---
        return {
            "relevant_chunks": jsonify_chunks(reranked_chunks),
            "session_id": session_id,
        }
