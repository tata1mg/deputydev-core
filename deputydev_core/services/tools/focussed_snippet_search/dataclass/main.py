from typing import List, Optional

from pydantic import BaseModel

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.dataclass.main import ChunkMetadata


class SearchTerm(BaseModel):
    keyword: str
    type: str
    file_path: Optional[str] = None


class FocussedSnippetSearchParams(BaseModel):
    repo_path: str
    search_terms: List[SearchTerm]


class FocussedSnippetSearchResponse(BaseModel):
    keyword: str
    type: str
    file_path: Optional[str] = None
    chunks: List[ChunkInfo]


class ChunkDetails(BaseModel):
    start_line: int
    end_line: int
    file_path: str
    file_hash: str
    meta_info: Optional[ChunkMetadata] = None


class CodeSnippetDetails(BaseModel):
    chunk_hash: str
    start_line: int
    end_line: int
    file_path: str


class FocusChunksParams(BaseModel):
    repo_path: str
    search_item_name: Optional[str] = None
    search_item_type: Optional[str] = None
    search_item_path: Optional[str] = None
    chunks: List[ChunkDetails | CodeSnippetDetails]


class AutoCompleteSearchParams(BaseModel):
    repo_path: str
    search_item_name: str
    search_item_type: str
    search_item_path: str
    chunk: ChunkDetails | None = None


class DirectoryStructureParams(BaseModel):
    repo_path: str
    directory_path: Optional[str] = None


class ChunkInfoAndHash(BaseModel):
    chunk_info: ChunkInfo
    chunk_hash: str

    def __hash__(self) -> int:
        return hash(self.chunk_hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChunkInfoAndHash):
            return False
        return self.chunk_hash == other.chunk_hash
