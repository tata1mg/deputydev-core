from weaviate.classes.config import DataType, Property, Tokenization

from deputydev_core.models.dao.weaviate.base import Base
from deputydev_core.models.dao.weaviate.constants.collection_names import (
    CHUNK_FILES_COLLECTION_NAME,
)


class ChunkFiles(Base):
    properties = [
        Property(
            name="file_path",
            data_type=DataType.TEXT,
            vectorize_property_name=False,
            skip_vectorization=True,
            tokenization=Tokenization.FIELD,
            index_filterable=True,
        ),
        Property(
            name="chunk_hash",
            data_type=DataType.TEXT,
            vectorize_property_name=False,
            tokenization=Tokenization.FIELD,
            skip_vectorization=True,
        ),
        Property(
            name="start_line",
            data_type=DataType.INT,
            vectorize_property_name=False,
            tokenization=None,
            skip_vectorization=True,
        ),
        Property(
            name="end_line",
            data_type=DataType.INT,
            vectorize_property_name=False,
            tokenization=None,
            skip_vectorization=True,
        ),
        Property(
            name="file_hash",
            data_type=DataType.TEXT,
            vectorize_property_name=False,
            tokenization=Tokenization.FIELD,
            skip_vectorization=True,
            index_filterable=True,
        ),
        Property(
            name="total_chunks",
            data_type=DataType.INT,
            vectorize_property_name=False,
            tokenization=None,
            skip_vectorization=True,
        ),
        Property(
            name="searchable_file_path",
            data_type=DataType.TEXT,
            vectorize_property_name=False,
            skip_vectorization=True,
            tokenization=Tokenization.TRIGRAM,
            index_filterable=True,
            index_searchable=True,
        ),
        Property(
            name="searchable_file_name",
            data_type=DataType.TEXT,
            vectorize_property_name=False,
            skip_vectorization=True,
            tokenization=Tokenization.TRIGRAM,
            index_filterable=True,
            index_searchable=True,
        ),
        Property(
            name="classes",
            data_type=DataType.TEXT_ARRAY,
            vectorize_property_name=False,
            tokenization=Tokenization.TRIGRAM,
            skip_vectorization=True,
            index_filterable=True,
            index_searchable=True,
        ),
        Property(
            name="functions",
            data_type=DataType.TEXT_ARRAY,
            vectorize_property_name=False,
            tokenization=Tokenization.TRIGRAM,
            skip_vectorization=True,
            index_filterable=True,
            index_searchable=True,
        ),
        Property(
            name="meta_info",
            data_type=DataType.OBJECT,
            vectorize_property_name=False,
            tokenization=None,
            skip_vectorization=True,
            index_filterable=False,
            index_searchable=False,
            nested_properties=[
                Property(
                    name="hierarchy",
                    data_type=DataType.OBJECT_ARRAY,
                    nested_properties=[
                        Property(name="type", data_type=DataType.TEXT),
                        Property(name="value", data_type=DataType.TEXT),
                        Property(name="is_breakable_node", data_type=DataType.BOOL),
                    ],
                ),
            ],
        ),
        Property(
            name="has_imports",
            data_type=DataType.BOOL,
            vectorize_property_name=False,
            skip_vectorization=True,
        ),
    ]
    collection_name = CHUNK_FILES_COLLECTION_NAME
