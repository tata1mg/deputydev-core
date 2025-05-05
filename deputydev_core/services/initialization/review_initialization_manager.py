import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Dict, Type

from deputydev_core.clients.http.service_clients.one_dev_review_client import OneDevReviewClient
from deputydev_core.services.chunking.chunker.handlers.vector_db_chunker import VectorDBChunker
from deputydev_core.services.chunking.vector_store.chunk_vector_store_cleanup_manager import (
    ChunkVectorStoreCleaneupManager,
)
from deputydev_core.services.initialization.initialization_service import InitializationManager
from deputydev_core.services.repository.dataclasses.main import WeaviateSyncAndAsyncClients
from deputydev_core.utils.custom_progress_bar import CustomProgressBar


from prompt_toolkit.shortcuts.progress_bar import ProgressBar
from weaviate import WeaviateAsyncClient, WeaviateClient
from weaviate.connect import ConnectionParams, ProtocolParams
from weaviate.embedded import EmbeddedOptions

from deputydev_core.services.embedding.base_one_dev_embedding_manager import (
    BaseOneDevEmbeddingManager,
)
from deputydev_core.services.embedding.pr_review_embedding_manager import PRReviewEmbeddingManager


class ReviewInitialisationManager(InitializationManager):
    def __init__(
            self,
            repo_path: Optional[str] = None,
            auth_token_key: Optional[str] = None,
            process_executor: Optional[ProcessPoolExecutor] = None,
            one_dev_client: Optional[OneDevReviewClient] = None,
            weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
            embedding_manager: Optional[Type[BaseOneDevEmbeddingManager]] = None,
    ) -> None:
        super().__init__(repo_path, auth_token_key, process_executor, one_dev_client, weaviate_client, PRReviewEmbeddingManager)

    async def prefill_vector_store(
            self,
            chunkable_files_and_hashes: Dict[str, str],
            progressbar: Optional[CustomProgressBar] = None,
            enable_refresh: Optional[bool] = False,
    ) -> None:
        if not self.local_repo:
            raise ValueError("Local repo is not initialized")

        if not self.weaviate_client:
            raise ValueError("Connect to vector store")

        all_chunks = await VectorDBChunker(
            local_repo=self.local_repo,
            weaviate_client=self.weaviate_client,
            embedding_manager=self.embedding_manager,
            process_executor=self.process_executor,
            chunkable_files_and_hashes=chunkable_files_and_hashes,
        ).create_chunks_and_docs()

        # start chunk cleanup
        self.chunk_cleanup_task = asyncio.create_task(
            ChunkVectorStoreCleaneupManager(
                exclusion_chunk_hashes=[chunk.content_hash for chunk in all_chunks],
                weaviate_client=self.weaviate_client,
            ).start_cleanup_for_chunk_and_hashes()
        )
