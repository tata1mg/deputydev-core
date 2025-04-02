from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class AutoCompleteSearchRecords(Enum):
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    FILE_PATH = "FILE_PATH"


class RequestScope(Enum):
    SINGLE_QUERY = "SINGLE_QUERY"
    MULTI_QUERY = "MULTI_QUERY"


class SearchPath(BaseModel):
    file_path: str
    file_hash: str


class Search(BaseModel):
    keyword: str
    search_record: AutoCompleteSearchRecords


class AutoCompleteSearch(BaseModel):
    keyword: str
    limit: int  # for performance purpose it is mandatory
    fuzzy: Optional[bool] = False
    search_paths: List[SearchPath]


class FocusedSearch(BaseModel):
    search_items: List[Search]
    limit: int  # for performance purpose it is mandatory
    search_paths: List[SearchPath]
