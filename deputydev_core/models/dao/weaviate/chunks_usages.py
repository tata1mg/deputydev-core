from weaviate.classes.config import DataType, Property, ReferenceProperty

from deputydev_core.models.dao.weaviate.base import Base
from deputydev_core.models.dao.weaviate.constants.collection_names import (
    CHUNK_USAGES_COLLECTION_NAME,
    CHUNKS_COLLECTION_NAME,
)


class ChunkUsages(Base):
    properties = [
        Property(
            name="last_usage_timestamp",
            data_type=DataType.DATE,
            vectorize_property_name=False,
            skip_vectorization=True,
            tokenization=None,
            index_range_filters=True,
        ),
    ]
    references = [
        ReferenceProperty(
            name="chunk",
            target_collection=CHUNKS_COLLECTION_NAME,
        )
    ]
    collection_name = CHUNK_USAGES_COLLECTION_NAME
