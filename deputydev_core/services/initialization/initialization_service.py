import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple, Type

from prompt_toolkit.shortcuts.progress_bar import ProgressBar

from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.chunker.handlers.one_dev_cli_chunker import (
    OneDevCLIChunker,
)
from deputydev_core.services.chunking.vector_store.chunk_vector_store_cleanup_manager import (
    ChunkVectorStoreCleaneupManager,
)
from deputydev_core.services.embedding.base_one_dev_embedding_manager import (
    BaseOneDevEmbeddingManager,
)
from deputydev_core.services.embedding.cli_embedding_manager import CLIEmbeddingManager
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

class InitializationManager:
    def __init__(
        self,
        repo_path: Optional[str] = None,
        auth_token_key: Optional[str] = None,
        process_executor: Optional[ProcessPoolExecutor] = None,
        one_dev_client: Optional[OneDevClient] = None,
        weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
        embedding_manager: Optional[Type[BaseOneDevEmbeddingManager]] = None,
    ) -> None:
        self.repo_path = repo_path
        self.weaviate_client: Optional[WeaviateSyncAndAsyncClients] = weaviate_client
        self.local_repo = None
        # it was done to make CLI
        embedding_manager = embedding_manager or CLIEmbeddingManager
        self.embedding_manager = embedding_manager(auth_token_key=auth_token_key, one_dev_client=one_dev_client)
        self.process_executor = process_executor
        self.chunk_cleanup_task = None

    def get_local_repo(self, chunkable_files: List[str] = None) -> BaseLocalRepo:
        self.local_repo = LocalRepoFactory.get_local_repo(self.repo_path, chunkable_files=chunkable_files)
        return self.local_repo

    async def initialize_vector_db(
        self, should_clean: bool = False
    ) -> Tuple[WeaviateSyncAndAsyncClients, Optional[asyncio.subprocess.Process], bool]:
        """
        Initialize the vector database.
        This method will start the Weaviate process and create the necessary schema.
        If the process is already running, it will skip starting it again.
        """
        return await WeaviateInitializer().initialize(should_clean=should_clean)

    async def prefill_vector_store(
        self,
        chunkable_files_and_hashes: Dict[str, str],
        progressbar: Optional[ProgressBar] = None,
        enable_refresh: Optional[bool] = False,
    ) -> None:
        assert self.local_repo, "Local repo is not initialized"
        assert self.weaviate_client, "Connect to vector store"

        all_chunks = await OneDevCLIChunker(
            local_repo=self.local_repo,
            weaviate_client=self.weaviate_client,
            embedding_manager=self.embedding_manager,
            process_executor=self.process_executor,
            progress_bar=progressbar,
            chunkable_files_and_hashes=chunkable_files_and_hashes,
        ).create_chunks_and_docs(enable_refresh=enable_refresh)

        if enable_refresh:
            self.process_chunks_cleanup(all_chunks)

    def process_chunks_cleanup(self, all_chunks: List[ChunkInfo]):
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

    def get_required_collections(self):
        raise NotImplemented