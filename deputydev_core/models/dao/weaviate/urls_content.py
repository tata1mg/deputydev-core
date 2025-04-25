from weaviate.classes.config import DataType, Property, Tokenization

from deputydev_core.models.dao.weaviate.base import Base
from deputydev_core.models.dao.weaviate.constants.collection_names import (
    URLS_CONTENT,
)


class UrlsContent(Base):
    properties = [
        Property(
            name="name",
            data_type=DataType.TEXT,
            tokenization=Tokenization.TRIGRAM,
            vectorize_property_name=False,
            skip_vectorization=True,
            index_searchable=True,
            index_filterable=True,
        ),
        Property(
            name="url",
            data_type=DataType.TEXT,
            tokenization=Tokenization.TRIGRAM,
            vectorize_property_name=False,
            skip_vectorization=True,
            index_filterable=True,
            index_searchable=True,
        ),
        Property(
            name="content",
            data_type=DataType.TEXT,
            tokenization=Tokenization.FIELD,
            vectorize_property_name=False,
            skip_vectorization=False,
            index_searchable=False,
            index_filterable=False,
        ),
        Property(
            name="last_indexed",
            vectorize_property_name=False,
            data_type=DataType.DATE,
            skip_vectorization=True,
            index_filterable=True,
        ),
        Property(
            name="content_hash",
            vectorize_property_name=False,
            data_type=DataType.TEXT,
            tokenization=Tokenization.FIELD,
            skip_vectorization=True,
            index_filterable=True,
        ),
        Property(
            name="cache_headers",
            vectorize_property_name=False,
            data_type=DataType.OBJECT,
            tokenization=None,
            skip_vectorization=True,
            index_filterable=True,
            nested_properties=[
                Property(name="etag", data_type=DataType.TEXT),
                Property(name="last_modified", data_type=DataType.TEXT),
            ],
        ),
        Property(
            name="backend_id",
            vectorize_property_name=False,
            data_type=DataType.INT,
            tokenization=None,
            skip_vectorization=True,
            index_filterable=True,
        ),
    ]

    collection_name = URLS_CONTENT
