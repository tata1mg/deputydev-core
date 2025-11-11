from pydantic import BaseModel, ConfigDict
from weaviate import WeaviateAsyncClient, WeaviateClient

from deputydev_core.utils.app_logger import AppLogger


class WeaviateSyncAndAsyncClients(BaseModel):
    sync_client: WeaviateClient
    async_client: WeaviateAsyncClient

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def is_ready(self) -> bool:
        try:
            async_ready = await self.async_client.is_ready()
            # sync_client.is_ready() is probably synchronous — don’t await
            sync_ready = self.sync_client.is_ready()
            return async_ready and sync_ready
        except Exception:  # noqa: BLE001
            AppLogger.log_error("Failed to check if weaviate is ready")
            return False

    async def ensure_connected(self) -> None:
        if not await self.is_ready():
            self.async_client.connect()
            self.sync_client.connect()
