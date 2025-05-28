import asyncio
from typing import Optional, Tuple
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.services.initialization.vector_store.weaviate.weaviate_connector_factory import (
    WeaviateConnectorFactory,
)
from deputydev_core.utils.config_manager import ConfigManager


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
            env_variables=ConfigManager.configs["WEAVIATE_ENV_VARIABLES"],
        )
        new_weaviate_process = await connector.initialize()
        self.weaviate_client = connector.weaviate_client

        if new_weaviate_process:
            await self._change_weaviate_process(new_weaviate_process=new_weaviate_process)

    async def initialize(
        self,
    ) -> Tuple[WeaviateSyncAndAsyncClients, Optional[asyncio.subprocess.Process]]:
        """
        Initialize the Weaviate client and schema. If the schema version is not the same as the current version,
        the schema will be cleaned and recreated.
        """
        await self._spin_up_and_establish_weaviate_connection()
        if not self.weaviate_client or not await self.weaviate_client.is_ready():
            raise ValueError("Connect to vector store failed")
        return self.weaviate_client, self.weaviate_process
