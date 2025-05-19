from sanic import Sanic
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.services.initialization.initialization_service import (
        InitializationManager,
)
from deputydev_core.services.repository.dataclasses.main import (
        WeaviateSyncAndAsyncClients,
    )



async def weaviate_connection():
    app = Sanic.get_app()
    if not hasattr(app.ctx, "weaviate_client"):
        return
    if app.ctx.weaviate_client:
        weaviate_clients: "WeaviateSyncAndAsyncClients" = app.ctx.weaviate_client
        if not weaviate_clients.async_client.is_connected():
            print("Async Connection was dropped, Reconnecting")
            await weaviate_clients.async_client.connect()
        if not weaviate_clients.sync_client.is_connected():
            print("Sync Connection was dropped, Reconnecting")
            weaviate_clients.sync_client.connect()
        return weaviate_clients


async def get_weaviate_client(initialization_manager: InitializationManager) -> "WeaviateSyncAndAsyncClients":
    weaviate_client = await weaviate_connection()
    if weaviate_client:
        weaviate_client = weaviate_client
    else:
        weaviate_client, _new_weaviate_process, _schema_cleaned = await initialization_manager.initialize_vector_db()
    return weaviate_client

async def clean_weaviate_collections(initialization_manager: InitializationManager) -> None:
    """
    Cleans all collections from Weaviate using the sync client.
    Initializes the vector DB clients if not already available.
    """
    weaviate_client = await get_weaviate_client(initialization_manager)

    if not weaviate_client.sync_client:
        raise ValueError("Weaviate sync client is not initialized")

    AppLogger.log_debug("Cleaning up Weaviate sync collections")
    weaviate_client.sync_client.collections.delete_all()