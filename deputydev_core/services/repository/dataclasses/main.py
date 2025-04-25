import asyncio
from pydantic import BaseModel, ConfigDict
from weaviate import WeaviateAsyncClient, WeaviateClient
from typing import ClassVar, Optional

from deputydev_core.utils.app_logger import AppLogger


class WeaviateSyncAndAsyncClients(BaseModel):
    sync_client: WeaviateClient
    async_client: WeaviateAsyncClient
    weaviate_process: ClassVar[Optional[asyncio.subprocess.Process]]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def is_ready(self) -> bool:
        try:
            async_ready = await self.async_client.is_ready()
            sync_ready = self.sync_client.is_ready()
            return async_ready and sync_ready
        except Exception:
            AppLogger.log_error("Failed to check if weaviate is ready")
            return False

    async def ensure_connected(self):
        if not await self.is_ready():
            await self.async_client.connect()
            self.sync_client.connect()
