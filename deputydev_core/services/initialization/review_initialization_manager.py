from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional, Type, List, Tuple, Union

from deputydev_core.models.dao.weaviate.chunk_files import ChunkFiles
from deputydev_core.models.dao.weaviate.chunks import Chunks
from deputydev_core.models.dao.weaviate.weaviate_schema_details import (
    WeaviateSchemaDetails,
)

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
        one_dev_client=None,
        weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
        embedding_manager: Optional[Type[BaseOneDevEmbeddingManager]] = None,
    ) -> None:
        super().__init__(
            repo_path, auth_token_key, process_executor, one_dev_client, weaviate_client, PRReviewEmbeddingManager
        )

    async def initialize_vector_db(self) -> WeaviateSyncAndAsyncClients:
        await super().initialize_vector_db()
        self._sync_schema_and_return_cleanup_status()
        return self.weaviate_client

    async def _sync_schema_and_return_cleanup_status(self):
        await self._populate_collections()