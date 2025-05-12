from sanic import Sanic

from deputydev_core.services.initialization.initialization_service import (
    InitializationManager,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.utils.constants.enums import ContextValueKeys
from deputydev_core.utils.context_value import ContextValue


async def weaviate_connection():
    weaviate_clients: WeaviateSyncAndAsyncClients = ContextValue.get(ContextValueKeys.WEAVIATE_CLIENT.value)

    if weaviate_clients:
        if not weaviate_clients.async_client.is_connected():
            print("Async Connection was dropped, Reconnecting")
            await weaviate_clients.async_client.connect()
        if not weaviate_clients.sync_client.is_connected():
            print("Sync Connection was dropped, Reconnecting")
            weaviate_clients.sync_client.connect()
        return weaviate_clients


async def initialise_weaviate_client(initialization_manager: "InitializationManager") -> "WeaviateSyncAndAsyncClients":
    weaviate_client = await weaviate_connection()
    if weaviate_client:
        weaviate_client = weaviate_client
    else:
        weaviate_client, _new_weaviate_process, _schema_cleaned = await initialization_manager.initialize_vector_db()
    return weaviate_client
