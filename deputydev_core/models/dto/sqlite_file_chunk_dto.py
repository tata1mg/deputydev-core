from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class FileDTO(BaseModel):
    id: Optional[int] = None
    repo_path: str
    file_path: str
    file_name: str
    file_hash: str
    language: Optional[str] = None
    num_lines: Optional[int] = None
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    metadata_json: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChunkDTO(BaseModel):
    id: Optional[int] = None
    file_id: int
    node_name: str
    node_type: Optional[str] = None
    category: Literal["function", "class", "import"]
    start_line: int
    end_line: int
    parent_name: Optional[str] = None
    parent_type: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
