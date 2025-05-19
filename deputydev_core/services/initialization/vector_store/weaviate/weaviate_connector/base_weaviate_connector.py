import asyncio
import os
import traceback
from pathlib import Path
from typing import Any, Optional

import aiohttp

from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)

from weaviate.embedded import EmbeddedOptions
from weaviate import WeaviateAsyncClient, WeaviateClient
from weaviate.config import AdditionalConfig, Timeout
from weaviate.connect import ConnectionParams, ProtocolParams

from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.config_manager import ConfigManager

class BaseWeaviateConnector:
    def __init__(
        self,
        base_dir: str,
        weaviate_version: str,
        weaviate_host: str,
        weaviate_http_port: int,
        weaviate_grpc_port: int,
        startup_timeout: int,
        startup_healthcheck_interval: int,
        env_variables: dict[str, Any]
    ) -> None:
        self.weaviate_version = weaviate_version
        self.base_dir = os.path.expanduser(base_dir)
        self.persistence_data_path = os.path.expanduser(env_variables['PERSISTENCE_DATA_PATH'])
        self.weaviate_host = weaviate_host
        self.weaviate_http_port = weaviate_http_port
        self.weaviate_grpc_port = weaviate_grpc_port
        self.startup_timeout = startup_timeout
        self.startup_healthcheck_interval = startup_healthcheck_interval
        self.env_variables = env_variables
        self.connection_params = self.get_connection_params()
        self.additional_config = self.get_additional_config()
        self.embedded_options = self.get_embedded_options()
        self.weaviate_client: Optional[WeaviateSyncAndAsyncClients] = None

    def get_sync_client(self) -> WeaviateClient:
        if self.weaviate_client and self.weaviate_client.sync_client:
            return self.weaviate_client.sync_client

        sync_client = WeaviateClient(
            connection_params=self.connection_params,
             additional_config=self.additional_config,
        )
        sync_client.connect()
        return sync_client

    async def get_async_client(self) -> WeaviateAsyncClient:
        if self.weaviate_client and self.weaviate_client.async_client:
            return self.weaviate_client.async_client

        async_client: Optional[WeaviateAsyncClient] = None

        try:
            async_client = WeaviateAsyncClient(
                embedded_options=self.embedded_options,
                additional_config=self.additional_config,
            )
            await async_client.connect()
        except Exception as _ex:
            if (
                    "Embedded DB did not start because processes are already listening on ports http:8079 and grpc:50050"
                    in str(_ex)
            ):
                async_client = WeaviateAsyncClient(
                    connection_params=self.connection_params,
                    additional_config=self.additional_config,
                )
                await async_client.connect()
            else:
                AppLogger.log_info(traceback.format_exc())
                AppLogger.log_error(f"Failed to connect to vector store: {str(_ex)}")
                raise _ex

        return async_client

    def get_embedded_options(self):
        resolved_binary_path = Path(ConfigManager.configs["WEAVIATE_EMBEDDED_DB_BINARY_PATH"]).expanduser().resolve()

        return EmbeddedOptions(
            persistence_data_path=self.persistence_data_path,
            binary_path=str(resolved_binary_path),
            hostname=ConfigManager.configs["WEAVIATE_HOST"],
            port=ConfigManager.configs["WEAVIATE_HTTP_PORT"],
            grpc_port=ConfigManager.configs["WEAVIATE_GRPC_PORT"],
            version="1.27.0",
            additional_env_vars={
                "LOG_LEVEL": self.env_variables['LOG_LEVEL'],
            },
        )

    def get_connection_params(self):
        return ConnectionParams(
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

    def get_additional_config(self):
        timeouts = ConfigManager.configs["WEAVIATE_CLIENT_TIMEOUTS"]
        return AdditionalConfig(
            timeout=Timeout(init=timeouts["INIT"], query=timeouts["QUERY"], insert=timeouts["INSERT"]),
        )

    async def _is_weaviate_running(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.weaviate_host}:{self.weaviate_http_port}/v1/.well-known/ready"
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            AppLogger.log_debug(f"Error checking Weaviate status: {str(e)}")
            return False

    async def wait_for_weaviate_ready(self) -> bool:
        """Check for weaviate to be up every given interval for a maximum of given timeout"""
        loop = asyncio.get_running_loop()
        start = loop.time()

        while True:
            now = loop.time()
            if now - start > self.startup_timeout:
                raise TimeoutError("Weaviate startup timed out")
            if await self._is_weaviate_running():
                return True

            await asyncio.sleep(self.startup_healthcheck_interval)

    async def initialize(self):
        async_client = await self.get_async_client()
        sync_client = self.get_sync_client()
        self.weaviate_client = WeaviateSyncAndAsyncClients(
            async_client=async_client,
            sync_client=sync_client,
        )


