import traceback
from typing import Optional

from weaviate.classes.query import Filter
from weaviate.util import generate_uuid5

from deputydev_core.models.dao.weaviate.weaviate_schema_details import (
    WeaviateSchemaDetails,
)
from deputydev_core.services.repository.base_weaviate_repository import (
    BaseWeaviateRepository,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.utils.app_logger import AppLogger


class WeaviateSchemaDetailsService(BaseWeaviateRepository):
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients):
        super().__init__(weaviate_client, WeaviateSchemaDetails.collection_name)
        self.CONSTANT_HASH = "weaviate_schema_details"

    async def get_schema_version(self) -> Optional[int]:
        try:
            await self.ensure_collection_connections()
            schema_details = self.sync_collection.query.fetch_objects(
                filters=Filter.by_id().equal(generate_uuid5(self.CONSTANT_HASH))
            )
            return schema_details.objects[0].properties["version"]
        except Exception:
            return None

    async def set_schema_version(self, schema_version: int) -> None:
        try:
            await self.ensure_collection_connections()
            self.sync_collection.data.insert(
                uuid=generate_uuid5(self.CONSTANT_HASH),
                properties={"version": schema_version},
            )
        except Exception:
            AppLogger.log_debug(traceback.format_exc())
