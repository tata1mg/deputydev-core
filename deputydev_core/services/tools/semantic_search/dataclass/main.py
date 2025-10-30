from typing import List, Optional

from pydantic import BaseModel


class SemanticSearchParams(BaseModel):
    repo_path: str
    query: str
    explanation: str
    session_id: int
    session_type: str
    focus_directories: Optional[List[str]] = None
