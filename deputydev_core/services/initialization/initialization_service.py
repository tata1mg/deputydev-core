import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import List, Optional, Type

from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
from deputydev_core.models.dao.weaviate.base import Base as WeaviateBaseDAO
from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.vector_store.chunk_vector_store_cleanup_manager import (
    ChunkVectorStoreCleaneupManager,
)
from deputydev_core.services.embedding.base_one_dev_embedding_manager import (
    BaseOneDevEmbeddingManager,
)
from deputydev_core.services.initialization.vector_store.weaviate.constants.weaviate_constants import (
    WEAVIATE_SCHEMA_VERSION,
)
from deputydev_core.services.initialization.vector_store.weaviate.weaviate_initializer import (
    WeaviateInitializer,
)
from deputydev_core.services.repo.local_repo.base_local_repo_service import (
    BaseLocalRepo,
)
from deputydev_core.services.repo.local_repo.local_repo_factory import LocalRepoFactory
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.services.repository.weaaviate_schema_details.weaviate_schema_details_service import (
    WeaviateSchemaDetailsService,
)


class InitializationManager:
    def __init__(
        self,
        embedding_manager: Type[BaseOneDevEmbeddingManager],
        repo_path: Optional[str] = None,
        auth_token_key: Optional[str] = None,
        process_executor: Optional[ProcessPoolExecutor] = None,
        one_dev_client: Optional[OneDevClient] = None,
        weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
        ripgrep_path: Optional[str] = None,
    ) -> None:
        self.repo_path = repo_path
        self.weaviate_client: Optional[WeaviateSyncAndAsyncClients] = weaviate_client
        self.local_repo = None
        # it was done to make CLI
        self.embedding_manager = embedding_manager(auth_token_key=auth_token_key, one_dev_client=one_dev_client)
        self.process_executor = process_executor
        self.chunk_cleanup_task = None
        self.ripgrep_path = ripgrep_path

    def get_local_repo(self, chunkable_files: Optional[List[str]] = None) -> BaseLocalRepo:
        self.local_repo = LocalRepoFactory.get_local_repo(
            self.repo_path, chunkable_files=chunkable_files, ripgrep_path=self.ripgrep_path
        )
        return self.local_repo

    async def initialize_vector_db(self) -> None:
        """
        Initialize the vector database.
        This method will start the Weaviate process and create the necessary schema.
        If the process is already running, it will skip starting it again.
        """
        (
            self.weaviate_client,
            self.weaviate_process,
        ) = await WeaviateInitializer().initialize()

    def process_chunks_cleanup(self, all_chunks: List[ChunkInfo]) -> None:
        """
        Process chunk clean ups if process_clean_up is true

        Parameters:
            all_chunks (List[ChunkInfo):
        """

        # clean up the code if only process clean up is true
        # this was done for performance to allow clean up for certain types of events only
        # as this is resource intensive
        # start chunk cleanup process in background
        self.chunk_cleanup_task = asyncio.create_task(
            ChunkVectorStoreCleaneupManager(
                exclusion_chunk_hashes=[chunk.content_hash for chunk in all_chunks],
                weaviate_client=self.weaviate_client,
            ).start_cleanup_for_chunk_and_hashes()
        )

    async def _check_and_initialize_collection(self, collection: Type[WeaviateBaseDAO]) -> None:
        if not self.weaviate_client:
            raise ValueError("Weaviate client is not initialized")
        exists = await self.weaviate_client.async_client.collections.exists(collection.collection_name)
        if not exists:
            await self.weaviate_client.async_client.collections.create(
                name=collection.collection_name,
                properties=collection.properties,
                references=collection.references if hasattr(collection, "references") else None,  # type: ignore
            )

    async def _populate_collections(self) -> None:
        await asyncio.gather(
            *[self._check_and_initialize_collection(collection=collection) for collection in self.collections]
        )

    async def _should_recreate_schema(self, should_clean: bool) -> bool:
        schema_version = await WeaviateSchemaDetailsService(weaviate_client=self.weaviate_client).get_schema_version()

        is_schema_invalid = schema_version is None or schema_version != WEAVIATE_SCHEMA_VERSION
        return should_clean or is_schema_invalid
