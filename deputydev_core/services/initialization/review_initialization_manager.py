import asyncio

from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Type, List, Tuple, Union


from deputydev_core.models.dao.weaviate.base import Base as WeaviateBaseDAO
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

    def get_required_collections(self) -> List[Type[WeaviateBaseDAO]]:
        return [Chunks, ChunkFiles, WeaviateSchemaDetails]

    async def initialize_vector_db(
        self, should_clean: bool = False, send_back_is_db_cleaned: bool = False
    ) -> Union[Tuple[WeaviateSyncAndAsyncClients, bool], WeaviateSyncAndAsyncClients]:
        if not self.weaviate_client:
            async_client = await self.initialize_vector_db_async()
            sync_client = self.initialize_vector_db_sync()

            self.weaviate_client = WeaviateSyncAndAsyncClients(
                async_client=async_client,
                sync_client=sync_client,
            )

            if not self.weaviate_client:
                raise ValueError("Connect to vector store failed")

        collections_to_initialize = self.get_required_collections()

        await asyncio.gather(
            *[
                self._check_and_initialize_collection(collection=collection)
                for collection in collections_to_initialize
            ]
        )

        return self.weaviate_client
