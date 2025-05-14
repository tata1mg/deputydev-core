from typing import List, Optional

from pydantic import BaseModel


class FilePathSearchPayload(BaseModel):
    repo_path: str
    directory: str
    search_terms: Optional[List[str]] = None
