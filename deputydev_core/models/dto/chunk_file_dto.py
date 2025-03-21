from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from deputydev_core.services.chunking.dataclass.main import ChunkMetadata


class ChunkFileData(BaseModel):
    chunk_hash: str
    file_path: str
    file_hash: str
    start_line: int
    end_line: int
    total_chunks: int
    meta_info: Optional[ChunkMetadata] = None


class ChunkFileDataWithSearchHelperKeys(ChunkFileData):
    classes: List[str]
    functions: List[str]
    searchable_file_path: str


class ChunkFileDTO(ChunkFileDataWithSearchHelperKeys):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
