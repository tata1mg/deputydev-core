from enum import Enum
from typing import List

from pydantic import BaseModel


class ChunkNodeType(Enum):
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"


class ChunkMetadataHierachyObject(BaseModel):
    type: ChunkNodeType
    value: str


class ChunkMetadata(BaseModel):
    hierarchy: List[ChunkMetadataHierachyObject]
    dechunk: bool
    import_only_chunk: bool
    all_functions: List[str]
    all_classes: List[str]
