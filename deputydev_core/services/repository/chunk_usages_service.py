import time
from datetime import datetime, timezone
from typing import List

from weaviate.classes.query import Filter, QueryReference
from weaviate.util import generate_uuid5

from deputydev_core.models.weaviate.chunks_usages import ChunkUsages
from repository.dataclasses.main import WeaviateSyncAndAsyncClients


class ChunkUsagesService:
    def __init__(self, weaviate_client: WeaviateSyncAndAsyncClients):
        self.weaviate_client = weaviate_client
        self.async_collection = weaviate_client.async_client.collections.get(ChunkUsages.collection_name)
        self.sync_collection = weaviate_client.sync_client.collections.get(ChunkUsages.collection_name)

    def usage_exixts(self, usage_hash: str) -> bool:
        try:
            usage_uuid = generate_uuid5(usage_hash)
            usages = self.sync_collection.query.fetch_objects_by_ids(ids=[usage_uuid], limit=1)
            return len(usages.objects) > 0
        except Exception as ex:
            raise ex

    def update_last_usage_timestamp(self, usage_hash: str) -> None:
        try:
            usage_uuid = generate_uuid5(usage_hash)
            self.sync_collection.data.update(
                properties={
                    "last_usage_timestamp": datetime.now().replace(tzinfo=timezone.utc),
                },
                uuid=usage_uuid,
            )
        except Exception as ex:
            raise ex

    def add_chunk_usage(self, chunk_hashes: List[str], usage_hash: str, force_create_references: bool = False) -> None:
        try:
            usage_uuid = generate_uuid5(usage_hash)
            time_start = time.perf_counter()
            if self.usage_exixts(usage_hash):
                self.update_last_usage_timestamp(usage_hash)

            else:
                with self.sync_collection.batch.dynamic() as _batch:
                    _batch.add_object(
                        properties={
                            "last_usage_timestamp": datetime.now().replace(tzinfo=timezone.utc),
                        },
                        uuid=usage_uuid,
                    )

            if not force_create_references:
                return

            with self.sync_collection.batch.dynamic() as _batch:
                for chunk_hash in chunk_hashes:
                    _batch.add_reference(
                        from_property="chunk",
                        from_uuid=usage_uuid,
                        to=generate_uuid5(chunk_hash),
                    )
        except Exception as ex:
            raise ex

    def get_removable_chunk_hashes(
            self, last_used_lt: datetime, chunk_hashes_to_skip: List[str], chunk_usage_hash_to_skip: List[str]
    ) -> List[str]:
        try:
            all_removable_usages = self.sync_collection.query.fetch_objects(
                filters=Filter.all_of(
                    [
                        Filter.by_property("last_usage_timestamp").less_than(last_used_lt),
                        Filter.all_of(
                            [
                                Filter.by_id().not_equal(generate_uuid5(skippable_hash))
                                for skippable_hash in chunk_usage_hash_to_skip
                            ]
                        ),
                    ]
                ),
                limit=10000,
                return_references=QueryReference(
                    link_on="chunk",
                    return_properties=["chunk_hash"],
                ),
            )

            all_removable_chunk_hashes: List[str] = []
            for chunk in all_removable_usages.objects:
                chunk_reference = chunk.references["chunk"]
                for chunk_obj in chunk_reference.objects:
                    if chunk_obj.properties["chunk_hash"] not in chunk_hashes_to_skip:
                        all_removable_chunk_hashes.append(chunk_obj.properties["chunk_hash"])

            return all_removable_chunk_hashes

        except Exception as ex:
            raise ex
