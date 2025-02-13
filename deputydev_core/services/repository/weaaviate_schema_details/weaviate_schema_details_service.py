import traceback
from typing import Optional

from weaviate.classes.query import Filter
from weaviate.util import generate_uuid5

from app.common.services.repository.dataclasses.main import WeaviateSyncAndAsyncClients
from app.common.utils.app_logger import AppLogger
from app.main.blueprints.deputydev_cli.models.weaviate.weaviate_schema_details import (
    WeaviateSchemaDetails,
)


class WeaviateSchemaDetailsService:
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients):
        self.weaviate_client = weaviate_client
        self.async_collection = weaviate_client.async_client.collections.get(WeaviateSchemaDetails.collection_name)
        self.sync_collection = weaviate_client.sync_client.collections.get(WeaviateSchemaDetails.collection_name)
        self.CONSTANT_HASH = "weaviate_schema_details"

    def get_schema_version(self) -> Optional[int]:
        try:
            schema_details = self.sync_collection.query.fetch_objects(
                filters=Filter.by_id().equal(generate_uuid5(self.CONSTANT_HASH))
            )
            return schema_details.objects[0].properties["version"]
        except Exception:
            return None

    def set_schema_version(self, schema_version: int) -> None:
        try:
            self.sync_collection.data.insert(
                uuid=generate_uuid5(self.CONSTANT_HASH),
                properties={"version": schema_version},
            )
        except Exception:
            AppLogger.log_debug(traceback.format_exc())
