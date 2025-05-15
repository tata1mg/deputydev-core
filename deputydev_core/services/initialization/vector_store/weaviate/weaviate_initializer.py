import asyncio
from typing import Optional, Tuple, Type

from deputydev_core.models.dao.weaviate.base import Base as WeaviateBaseDAO
from deputydev_core.models.dao.weaviate.chunk_files import ChunkFiles
from deputydev_core.models.dao.weaviate.chunks import Chunks
from deputydev_core.models.dao.weaviate.weaviate_schema_details import (
    WeaviateSchemaDetails,
)
from deputydev_core.services.initialization.vector_store.weaviate.constants.weaviate_constants import (
    WEAVIATE_SCHEMA_VERSION,
)

from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.services.repository.weaaviate_schema_details.weaviate_schema_details_service import (
    WeaviateSchemaDetailsService,
)
from deputydev_core.services.initialization.vector_store.weaviate.weaviate_connector_factory import WeaviateConnectorFactory
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.config_manager import ConfigManager
from deputydev_core.models.dao.weaviate.urls_content import UrlsContent


class WeaviateInitializer:
    def __init__(self) -> None:
        self.weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None
        self.weaviate_process: Optional[asyncio.subprocess.Process] = None

    async def _change_weaviate_process(self, new_weaviate_process: asyncio.subprocess.Process) -> None:
        if self.weaviate_process:
            self.weaviate_process.terminate()
            await self.weaviate_process.wait()

        self.weaviate_process = new_weaviate_process

    async def _spin_up_and_establish_weaviate_connection(self) -> None:
        if self.weaviate_client:
            return

        connector_class = WeaviateConnectorFactory.get_compatible_connector()
        connector = connector_class(
            base_dir=ConfigManager.configs["WEAVIATE_BASE_DIR"],
            weaviate_version=ConfigManager.configs["WEAVIATE_VERSION"],
            weaviate_host=ConfigManager.configs["WEAVIATE_HOST"],
            weaviate_http_port=ConfigManager.configs["WEAVIATE_HTTP_PORT"],
            weaviate_grpc_port=ConfigManager.configs["WEAVIATE_GRPC_PORT"],
            startup_timeout=ConfigManager.configs["WEAVIATE_STARTUP_TIMEOUT"],
            startup_healthcheck_interval=ConfigManager.configs["WEAVIATE_STARTUP_HEALTHCHECK_INTERVAL"],
            env_variables=ConfigManager.configs["WEAVIATE_ENV_VARIABLES"]
        )
        new_weaviate_process = await connector.initialize()
        self.weaviate_client = connector.weaviate_client

        if new_weaviate_process:
            await self._change_weaviate_process(new_weaviate_process=new_weaviate_process)

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

    async def _sync_schema_and_return_cleanup_status(self, should_clean: bool) -> bool:
        schema_version = await WeaviateSchemaDetailsService(weaviate_client=self.weaviate_client).get_schema_version()

        is_schema_invalid = schema_version is None or schema_version != WEAVIATE_SCHEMA_VERSION
        new_schema_creation = should_clean or is_schema_invalid

        if new_schema_creation:
            AppLogger.log_debug("Cleaning up the vector store")
            self.weaviate_client.sync_client.collections.delete_all()

        await asyncio.gather(
            *[
                self.__check_and_initialize_collection(collection=Chunks),
                self.__check_and_initialize_collection(collection=ChunkFiles),
                self.__check_and_initialize_collection(collection=WeaviateSchemaDetails),
                self.__check_and_initialize_collection(collection=UrlsContent)
            ]
        )

        if new_schema_creation:
            await WeaviateSchemaDetailsService(weaviate_client=self.weaviate_client).set_schema_version(
                WEAVIATE_SCHEMA_VERSION
            )

        return new_schema_creation

    async def initialize(
        self, should_clean: bool = False
    ) -> Tuple[WeaviateSyncAndAsyncClients, Optional[asyncio.subprocess.Process], bool]:
        """
        Initialize the Weaviate client and schema. If the schema version is not the same as the current version,
        the schema will be cleaned and recreated.
        """
        await self._spin_up_and_establish_weaviate_connection()
        new_schema_created = await self._sync_schema_and_return_cleanup_status(should_clean=should_clean)
        if not self.weaviate_client or not await self.weaviate_client.is_ready():
            raise ValueError("Connect to vector store failed")
        return self.weaviate_client, self.weaviate_process, new_schema_created
