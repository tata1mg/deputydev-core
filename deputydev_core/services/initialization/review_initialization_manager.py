from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional, Type

from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
from deputydev_core.models.dao.weaviate.chunk_files import ChunkFiles
from deputydev_core.models.dao.weaviate.chunks import Chunks
from deputydev_core.models.dao.weaviate.weaviate_schema_details import (
    WeaviateSchemaDetails,
)
from deputydev_core.services.chunking.chunker.handlers.vector_db_chunker import VectorDBChunker
from deputydev_core.services.embedding.base_one_dev_embedding_manager import (
    BaseOneDevEmbeddingManager,
)
from deputydev_core.services.embedding.pr_review_embedding_manager import (
    PRReviewEmbeddingManager,
)
from deputydev_core.services.initialization.initialization_service import (
    InitializationManager,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)


class ReviewInitialisationManager(InitializationManager):
    collections = [Chunks, ChunkFiles, WeaviateSchemaDetails]

    def __init__(
        self,
        repo_path: Optional[str] = None,
        auth_token_key: Optional[str] = None,
        process_executor: Optional[ProcessPoolExecutor] = None,
        one_dev_client: Optional[OneDevClient] = None,
        weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
        embedding_manager: Optional[Type[BaseOneDevEmbeddingManager]] = None,
    ) -> None:
        super().__init__(
            PRReviewEmbeddingManager,
            repo_path,
            auth_token_key,
            process_executor,
            one_dev_client,
            weaviate_client,
        )

    async def prefill_vector_store(
        self,
        chunkable_files_and_hashes: Dict[str, str],
        enable_refresh: Optional[bool] = False,
    ) -> None:
        assert self.local_repo, "Local repo is not initialized"
        assert self.weaviate_client, "Connect to vector store"

        if not self.process_executor:
            raise ValueError("Process executor is not initialized")

        all_chunks = await VectorDBChunker(
            local_repo=self.local_repo,
            process_executor=self.process_executor,
            weaviate_client=self.weaviate_client,
            embedding_manager=self.embedding_manager,
            chunkable_files_and_hashes=chunkable_files_and_hashes,
        ).create_chunks_and_docs(enable_refresh=enable_refresh or False)

        if enable_refresh:
            self.process_chunks_cleanup(all_chunks)

    async def initialize_vector_db(self) -> WeaviateSyncAndAsyncClients:
        await super().initialize_vector_db()
        self._sync_schema_and_return_cleanup_status()
        return self.weaviate_client

    async def _sync_schema_and_return_cleanup_status(self) -> None:
        await self._populate_collections()
