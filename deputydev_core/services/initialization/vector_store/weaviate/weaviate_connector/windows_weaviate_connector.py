import asyncio

from weaviate import WeaviateAsyncClient, WeaviateClient

from deputydev_core.services.initialization.vector_store.weaviate.weaviate_connector.base_weaviate_connector import (
    BaseWeaviateConnector,
)
from deputydev_core.utils.app_logger import AppLogger


class WindowsWeaviateConnector(BaseWeaviateConnector):
    DEFAULT_HTTP_PORT = 8080
    DEFAULT_GRPC_PORT = 50051

    async def initialize(self):
        weaviate_process = await self._spin_up_via_docker()
        await super().initialize()
        return weaviate_process

    async def get_async_client(self) -> WeaviateClient:
        "Without Embedding options for windows, since we spinup using docker on windows"
        if self.weaviate_client and self.weaviate_client.async_client:
            return self.weaviate_client.async_client

        async_client = WeaviateAsyncClient(
            connection_params=self.connection_params,
            additional_config=self.additional_config,
        )
        await async_client.connect()
        return async_client

    async def _spin_up_via_docker(self):
        if not await self._is_weaviate_running():
            AppLogger.log_info("Starting Weaviate binary")

            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--name",
                "weaviate",
                "-p",
                f"{str(self.weaviate_http_port)}:{self.DEFAULT_HTTP_PORT}",
                "-p",
                f"{str(self.weaviate_grpc_port)}:{self.DEFAULT_GRPC_PORT}",
                "-e",
                f"CLUSTER_ADVERTISE_ADDR={self.env_variables['CLUSTER_ADVERTISE_ADDR']}",
                "-e",
                f"LIMIT_RESOURCES={self.env_variables['LIMIT_RESOURCES']}",
                "-e",
                f"PERSISTENCE_DATA_PATH={self.persistence_data_path}",
                "-e",
                f"LOG_LEVEL={self.env_variables['LOG_LEVEL']}",
                "-e",
                f"DISK_USE_READONLY_PERCENTAGE={self.env_variables['DISK_USE_READONLY_PERCENTAGE']}",
                f"semitechnologies/weaviate:{self.weaviate_version}",
            ]

            weaviate_process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                await self.wait_for_weaviate_ready()
                AppLogger.log_info("Weaviate started successfully.")
                return weaviate_process
            except TimeoutError:
                weaviate_process.terminate()
                await weaviate_process.wait()
                raise RuntimeError("Weaviate failed to start within timeout")

        else:
            AppLogger.log_info("Weaviate is already running")
