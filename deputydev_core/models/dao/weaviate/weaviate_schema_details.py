from weaviate.classes.config import DataType, Property

from deputydev_core.models.dao.weaviate.base import Base

from .constants.collection_names import WEAVIATE_SCHEMA_DETAILS_COLLECTION_NAME


class WeaviateSchemaDetails(Base):
    properties = [
        Property(
            name="version",
            data_type=DataType.INT,
            vectorize_property_name=False,
            tokenization=None,
            skip_vectorization=True,
            index_filterable=False,
        ),
    ]
    collection_name = WEAVIATE_SCHEMA_DETAILS_COLLECTION_NAME
