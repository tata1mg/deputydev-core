from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)


class BaseWeaviateRepository:
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients, collection_name: str):
        self.weaviate_client = weaviate_client
        self.collection_name = collection_name
        self.async_collection = weaviate_client.async_client.collections.get(collection_name)
        self.sync_collection = weaviate_client.sync_client.collections.get(collection_name)

    async def ensure_collection_connections(self) -> None:
        await self.weaviate_client.ensure_connected()
        self.async_collection = self.weaviate_client.async_client.collections.get(self.collection_name)
        self.sync_collection = self.weaviate_client.sync_client.collections.get(self.collection_name)
