import asyncio
import platform

from typing import Optional, Type

from weaviate import WeaviateAsyncClient, WeaviateClient
from weaviate.connect import ConnectionParams, ProtocolParams
from weaviate.embedded import EmbeddedOptions
from weaviate.config import AdditionalConfig
from weaviate.config import Timeout

from deputydev_core.services.repository.weaaviate_schema_details.weaviate_schema_details_service import (
    WeaviateSchemaDetailsService,
)
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.constants.weaviate import WEAVIATE_SCHEMA_VERSION
from deputydev_core.utils.constants.weaviate import SupportedPlatforms
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.models.dao.weaviate.chunk_files import ChunkFiles
from deputydev_core.models.dao.weaviate.chunks import Chunks
from deputydev_core.models.dao.weaviate.weaviate_schema_details import (
    WeaviateSchemaDetails,
)
from deputydev_core.models.dao.weaviate.base import Base as WeaviateBaseDAO

from deputydev_core.services.vector_store.initializer.weaviate.weaviate_downloader import WeaviateDownloader


class WeaviateInitializer:
    def __init__(self,
        weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None
     ) -> None:
        self.weaviate_client: Optional[WeaviateSyncAndAsyncClients] = weaviate_client
    async def initialize(self, should_clean: bool = False) -> WeaviateSyncAndAsyncClients:
        self._spin_up_weaviate()
        self._sync_schema(should_clean)
        return self.weaviate_client

    async def _spin_up_weaviate(self):
        if self.weaviate_client:
            return self.weaviate_client

        weaviate_process = await WeaviateDownloader.download_and_run_weaviate()
        async_client = await self.get_async_client()
        sync_client = await self.get_sync_client()

        self.weaviate_client = WeaviateSyncAndAsyncClients(
            weaviate_process=weaviate_process,
            async_client=async_client,
            sync_client=sync_client,
        )

        if not self.weaviate_client.is_ready():  # TODO: To confirm why we were not checking is_ready here
            raise ValueError("Connect to vector store failed")

    async def _sync_schema(self, should_clean: bool):
        schema_version = await WeaviateSchemaDetailsService(weaviate_client=self.weaviate_client).get_schema_version()

        is_schema_invalid = schema_version is None or schema_version != WEAVIATE_SCHEMA_VERSION

        if should_clean or is_schema_invalid:
            AppLogger.log_debug("Cleaning up the vector store")
            self.weaviate_client.sync_client.collections.delete_all()

        await asyncio.gather(
            *[
                self.__check_and_initialize_collection(collection=Chunks),
                self.__check_and_initialize_collection(collection=ChunkFiles),
                self.__check_and_initialize_collection(collection=WeaviateSchemaDetails),
            ]
        )

        if should_clean or is_schema_invalid:
            await WeaviateSchemaDetailsService(weaviate_client=self.weaviate_client).set_schema_version(
                WEAVIATE_SCHEMA_VERSION
            )

    def get_sync_client(self) -> WeaviateClient:
        if self.weaviate_client and self.weaviate_client.sync_client:
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
                    port=50051,
                    secure=False,
                ),
            ),
            additional_config=AdditionalConfig(
                timeout=Timeout(init=30, query=60, insert=120),  # Values in seconds
            )
        )
        sync_client.connect()
        return sync_client

    async def get_async_client(self) -> WeaviateAsyncClient:
        if self.weaviate_client and self.weaviate_client.async_client:
            return self.weaviate_client.async_client

        async_client: Optional[WeaviateAsyncClient] = None
        resolved_persistence_data_path = Path(ConfigManager.configs["WEAVIATE_EMBEDDED_DB_PATH"]).expanduser().resolve()
        resolved_binary_path = Path(ConfigManager.configs["WEAVIATE_EMBEDDED_DB_BINARY_PATH"]).expanduser().resolve()

        # try:
        #     async_client = WeaviateAsyncClient(
        #         embedded_options=EmbeddedOptions(
        #             persistence_data_path=str(resolved_persistence_data_path),
        #             binary_path=str(resolved_binary_path),
        #             hostname=ConfigManager.configs["WEAVIATE_HOST"],
        #             port=ConfigManager.configs["WEAVIATE_HTTP_PORT"],
        #             grpc_port=ConfigManager.configs["WEAVIATE_GRPC_PORT"],
        #             version="1.27.0",
        #             additional_env_vars={
        #                 "LOG_LEVEL": "panic",
        #             },
        #         ),
        #         additional_config=AdditionalConfig(timeout=Timeout(init=20)),
        #     )
        #     await async_client.connect()
        # # except Exception as _ex:
        #     if (
        #         "Embedded DB did not start because processes are already listening on ports http:8079 and grpc:50050"
        #         in str(_ex)
        #     ):
        async_client = WeaviateAsyncClient(
            connection_params=ConnectionParams(
                http=ProtocolParams(
                    host=ConfigManager.configs["WEAVIATE_HOST"],
                    port=ConfigManager.configs["WEAVIATE_HTTP_PORT"],
                    secure=False,
                ),
                grpc=ProtocolParams(
                    host=ConfigManager.configs["WEAVIATE_HOST"],
                    port=50051,
                    secure=False,
                ),
            ),
            additional_config=AdditionalConfig(
                timeout=Timeout(init=30, query=60, insert=120),  # TODO: get these values from config
            )
        )
        await async_client.connect()

            # else:
            #     AppLogger.log_info(traceback.format_exc())
            #     AppLogger.log_error(f"Failed to connect to vector store: {str(_ex)}")
            #     raise _ex

        return async_client

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