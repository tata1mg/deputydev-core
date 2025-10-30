from typing import List, Optional

from pydantic import BaseModel


class SemanticSearchParams(BaseModel):
    repo_path: str
    query: str
    explanation: str
    focus_directories: Optional[List[str]] = None
    session_id: Optional[int] = None
    session_type: Optional[str] = None
