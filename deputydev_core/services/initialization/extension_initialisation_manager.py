import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Dict

from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
from deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker import OneDevExtensionChunker
from deputydev_core.services.chunking.vector_store.chunk_vector_store_cleanup_manager import \
    ChunkVectorStoreCleaneupManager
from deputydev_core.services.embedding.extension_embedding_manager import ExtensionEmbeddingManager
from deputydev_core.services.initialization.initialization_service import InitializationManager
from deputydev_core.services.repository.dataclasses.main import WeaviateSyncAndAsyncClients
from deputydev_core.utils.custom_progress_bar import CustomProgressBar


class ExtensionInitialisationManager(InitializationManager):
    def __init__(
            self,
            repo_path: Optional[str] = None,
            auth_token_key: Optional[str] = None,
            process_executor: Optional[ProcessPoolExecutor] = None,
            one_dev_client: Optional[OneDevClient] = None,
            weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,

    ) -> None:
        super().__init__(repo_path, auth_token_key, process_executor, one_dev_client, weaviate_client)
        self.embedding_manager = ExtensionEmbeddingManager(auth_token_key=auth_token_key, one_dev_client=one_dev_client)

    async def prefill_vector_store(
            self,
            chunkable_files_and_hashes: Dict[str, str],
            progressbar: Optional[CustomProgressBar] = None,
    ) -> None:
        if not self.local_repo:
            raise ValueError("Local repo is not initialized")

        if not self.weaviate_client:
            raise ValueError("Connect to vector store")

        all_chunks = await OneDevExtensionChunker(
            local_repo=self.local_repo,
            weaviate_client=self.weaviate_client,
            embedding_manager=self.embedding_manager,
            process_executor=self.process_executor,
            progress_bar=progressbar,
            chunkable_files_and_hashes=chunkable_files_and_hashes,
        ).create_chunks_and_docs()

        # start chunk cleanup
        self.chunk_cleanup_task = asyncio.create_task(
            ChunkVectorStoreCleaneupManager(
                exclusion_chunk_hashes=[chunk.content_hash for chunk in all_chunks],
                weaviate_client=self.weaviate_client,
            ).start_cleanup_for_chunk_and_hashes()
        )