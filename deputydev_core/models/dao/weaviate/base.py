from abc import ABC
from typing import Any, Dict, List

from weaviate.classes.config import DataType, Property, ReferenceProperty


class Base(ABC):
    properties: List[Property]
    references: List[ReferenceProperty]
    collection_name: str

    # this gives all the properties of the class to the instance
    @classmethod
    def get_weaviate_config(cls) -> Dict[str, Any]:
        return {
            "properties": cls.properties
            + [
                Property(
                    name="created_at",
                    data_type=DataType.DATE,
                    vectorize_property_name=False,
                    tokenization=None,
                ),
                Property(
                    name="updated_at",
                    data_type=DataType.DATE,
                    vectorize_property_name=False,
                    tokenization=None,
                ),
            ],
            "name": cls.collection_name,
        }
