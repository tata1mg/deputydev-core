from sanic import Sanic
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.services.initialization.initialization_service import (
        InitializationManager,
    )


async def weaviate_connection():
    app = Sanic.get_app()
    if app.ctx.weaviate_client:
        weaviate_clients: WeaviateSyncAndAsyncClients = app.ctx.weaviate_client
        if not weaviate_clients.async_client.is_connected():
            print(f"Async Connection was dropped, Reconnecting")
            await weaviate_clients.async_client.connect()
        if not weaviate_clients.sync_client.is_connected():
            print(f"Sync Connection was dropped, Reconnecting")
            weaviate_clients.sync_client.connect()
        return weaviate_clients


async def initialise_weaviate_client(initialization_manager: "InitializationManager") -> "WeaviateSyncAndAsyncClients":
    weaviate_client = await weaviate_connection()
    if weaviate_client:
        weaviate_client = weaviate_client
    else:
        weaviate_client = await initialization_manager.initialize_vector_db()
    return weaviate_client