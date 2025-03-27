from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional, Type

from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
from deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker import (
    OneDevExtensionChunker,
)
from deputydev_core.services.embedding.base_one_dev_embedding_manager import BaseOneDevEmbeddingManager
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


class ExtensionInitialisationManager(InitializationManager):
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
