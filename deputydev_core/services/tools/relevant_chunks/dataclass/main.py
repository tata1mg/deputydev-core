from typing import List, Optional

from pydantic import BaseModel


class RelevantChunksParams(BaseModel):
    repo_path: str
    query: str
    focus_chunks: Optional[List[str]] = []
    focus_files: Optional[List[str]] = []
    focus_directories: Optional[List[str]] = []
    perform_chunking: Optional[bool] = False
    session_id: Optional[int] = None
    session_type: Optional[str] = None
