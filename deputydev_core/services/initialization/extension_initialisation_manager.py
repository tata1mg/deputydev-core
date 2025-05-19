import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional, Type, Tuple

from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
from deputydev_core.models.dao.weaviate.chunk_files import ChunkFiles
from deputydev_core.models.dao.weaviate.chunks import Chunks
from deputydev_core.models.dao.weaviate.urls_content import UrlsContent
from deputydev_core.models.dao.weaviate.weaviate_schema_details import (
    WeaviateSchemaDetails,
)
from deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker import (
    OneDevExtensionChunker,
)
from deputydev_core.services.embedding.base_one_dev_embedding_manager import (
    BaseOneDevEmbeddingManager,
)
from deputydev_core.services.embedding.extension_embedding_manager import (
    ExtensionEmbeddingManager,
)
from deputydev_core.services.initialization.initialization_service import (
    InitializationManager,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.utils.custom_progress_bar import CustomProgressBar
from deputydev_core.services.initialization.vector_store.weaviate.constants.weaviate_constants import (
    WEAVIATE_SCHEMA_VERSION,
)
from deputydev_core.services.repository.weaaviate_schema_details.weaviate_schema_details_service import (
    WeaviateSchemaDetailsService,
)
from deputydev_core.utils.app_logger import AppLogger


class ExtensionInitialisationManager(InitializationManager):
    collections = [Chunks, ChunkFiles, WeaviateSchemaDetails, UrlsContent]

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
            repo_path, auth_token_key, process_executor, one_dev_client, weaviate_client, ExtensionEmbeddingManager
        )

    async def prefill_vector_store(
        self,
        chunkable_files_and_hashes: Dict[str, str],
        progressbar: Optional[CustomProgressBar] = None,
        enable_refresh: Optional[bool] = False,
    ) -> None:
        assert self.local_repo, "Local repo is not initialized"
        assert self.weaviate_client, "Connect to vector store"

        all_chunks = await OneDevExtensionChunker(
            local_repo=self.local_repo,
            weaviate_client=self.weaviate_client,
            embedding_manager=self.embedding_manager,
            process_executor=self.process_executor,
            progress_bar=progressbar,
            chunkable_files_and_hashes=chunkable_files_and_hashes,
        ).create_chunks_and_docs(enable_refresh=enable_refresh)

        if enable_refresh:
            self.process_chunks_cleanup(all_chunks)

    async def _sync_schema_and_return_cleanup_status(self, should_clean: bool) -> bool:
        is_new_schema = await self._should_recreate_schema(should_clean)

        if is_new_schema:
            AppLogger.log_debug("Cleaning up the vector store")
            self.weaviate_client.sync_client.collections.delete_all()

        await self._populate_collections()

        if is_new_schema:
            await WeaviateSchemaDetailsService(weaviate_client=self.weaviate_client).set_schema_version(
                WEAVIATE_SCHEMA_VERSION
            )

        return is_new_schema

    async def initialize_vector_db(
            self, should_clean: bool = False
    ) -> Tuple[WeaviateSyncAndAsyncClients, Optional[asyncio.subprocess.Process], bool]:
        """
        Initialize the vector database.
        This method will start the Weaviate process and create the necessary schema.
        If the process is already running, it will skip starting it again.
        """
        await super().initialize_vector_db()
        is_new_schema = await self._sync_schema_and_return_cleanup_status(should_clean=should_clean)
        return self.weaviate_client, self.weaviate_process, is_new_schema
