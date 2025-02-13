from pydantic import BaseModel, ConfigDict
from weaviate import WeaviateAsyncClient, WeaviateClient


class WeaviateSyncAndAsyncClients(BaseModel):
    sync_client: WeaviateClient
    async_client: WeaviateAsyncClient

    model_config = ConfigDict(arbitrary_types_allowed=True)
