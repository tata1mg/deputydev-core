import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional, Type
from weaviate import WeaviateAsyncClient, WeaviateClient
from weaviate.connect import ConnectionParams, ProtocolParams
from weaviate.embedded import EmbeddedOptions

from models.weaviate.base import Base as WeaviateBaseDAO
from models.weaviate.chunk_files import ChunkFiles
from models.weaviate.chunks import Chunks
from models.weaviate.chunks_usages import ChunkUsages
from repository.dataclasses.main import WeaviateSyncAndAsyncClients
from clients.one_dev_client import OneDevClient
from managers.one_dev_embedding_manager import OneDevEmbeddingManager
from utils.config_manager import ConfigManager

class InitializationManager:
    def __init__(
            self,
            repo_path: str = None,
            auth_token: str = None,
            process_executor: ProcessPoolExecutor = None,
            one_dev_client: OneDevClient = None,
            weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None,
    ) -> None:
        self.repo_path = repo_path
        self.weaviate_client: Optional[WeaviateSyncAndAsyncClients] = weaviate_client
        self.local_repo = None
        self.embedding_manager = OneDevEmbeddingManager(auth_token=auth_token, one_dev_client=one_dev_client)
        self.process_executor = process_executor
        self.chunk_cleanup_task = None

    async def __check_and_initialize_collection(self, collection: Type[WeaviateBaseDAO]) -> None:
        if not self.weaviate_client:
            raise ValueError("Weaviate client is not initialized")
        exists = await self.weaviate_client.async_client.collections.exists(collection.collection_name)
        if not exists:
            await self.weaviate_client.async_client.collections.create(
                name=collection.collection_name,
                properties=collection.properties,
                references=collection.references if hasattr(collection, "references") else None,  # type: ignore
            )

    async def initialize_vector_db_async(self) -> WeaviateAsyncClient:
        if self.weaviate_client and self.weaviate_client.async_client:
            return self.weaviate_client.async_client

        async_client: Optional[WeaviateAsyncClient] = None
        try:
            async_client = WeaviateAsyncClient(
                embedded_options=EmbeddedOptions(
                    hostname=ConfigManager.configs["WEAVIATE_HOST"],
                    port=ConfigManager.configs["WEAVIATE_HTTP_PORT"],
                    grpc_port=ConfigManager.configs["WEAVIATE_GRPC_PORT"],
                    version="1.27.0",
                    additional_env_vars={
                        "LOG_LEVEL": "panic",
                    },
                ),
            )
            await async_client.connect()
        except Exception as _ex:
            if (
                    "Embedded DB did not start because processes are already listening on ports http:8079 and grpc:50050"
                    in str(_ex)
            ):
                async_client = WeaviateAsyncClient(
                    connection_params=ConnectionParams(
                        http=ProtocolParams(
                            host=ConfigManager.configs["WEAVIATE_HOST"],
                            port=ConfigManager.configs["WEAVIATE_HTTP_PORT"],
                            secure=False,
                        ),
                        grpc=ProtocolParams(
                            host=ConfigManager.configs["WEAVIATE_HOST"],
                            port=ConfigManager.configs["WEAVIATE_GRPC_PORT"],
                            secure=False,
                        ),
                    )
                )
                await async_client.connect()

        if not async_client:
            raise Exception("async client not initialized")
        return async_client

    def initialize_vector_db_sync(self) -> WeaviateClient:
        if self.weaviate_client and self.weaviate_client.async_client:
            return self.weaviate_client.sync_client

        sync_client = WeaviateClient(
            connection_params=ConnectionParams(
                http=ProtocolParams(
                    host=ConfigManager.configs["WEAVIATE_HOST"],
                    port=ConfigManager.configs["WEAVIATE_HTTP_PORT"],
                    secure=False,
                ),
                grpc=ProtocolParams(
                    host=ConfigManager.configs["WEAVIATE_HOST"],
                    port=ConfigManager.configs["WEAVIATE_GRPC_PORT"],
                    secure=False,
                ),
            )
        )
        sync_client.connect()
        return sync_client

    async def initialize_vector_db(self, should_clean: bool = False) -> WeaviateSyncAndAsyncClients:
        if self.weaviate_client:
            return self.weaviate_client
        async_client = await self.initialize_vector_db_async()
        sync_client = self.initialize_vector_db_sync()

        self.weaviate_client = WeaviateSyncAndAsyncClients(
            async_client=async_client,
            sync_client=sync_client,
        )

        if should_clean:
            self.weaviate_client.sync_client.collections.delete_all()

        await asyncio.gather(
            *[
                self.__check_and_initialize_collection(collection=Chunks),
                self.__check_and_initialize_collection(collection=ChunkFiles),
                self.__check_and_initialize_collection(collection=ChunkUsages),
            ]
        )

        if not self.weaviate_client:
            raise ValueError("Connect to vector store failed")

        return self.weaviate_client
