from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChunkFileDTO(BaseModel):
    id: Optional[str] = None
    chunk_hash: str
    file_path: str
    file_hash: str
    start_line: int
    end_line: int
    total_chunks: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
