from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from deputydev_core.services.chunking.dataclass.main import ChunkMetadata


class ChunkFileDTO(BaseModel):
    id: Optional[str] = None
    chunk_hash: str
    file_path: str
    file_hash: str
    start_line: int
    end_line: int
    total_chunks: int
    classes: List[str]
    functions: List[str]
    entities: str
    meta_info: Optional[ChunkMetadata]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
