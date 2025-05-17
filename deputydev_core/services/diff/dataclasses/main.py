from enum import Enum
from typing import Annotated, List, Literal, Tuple, Union

from pydantic import BaseModel, Field


class DiffTypes(str, Enum):
    UDIFF = "UDIFF"
    LINE_NUMBERED = "LINE_NUMBERED"
    SEARCH_AND_REPLACE = "SEARCH_AND_REPLACE"


class UdiffData(BaseModel):
    type: Literal[DiffTypes.UDIFF]
    incremental_udiff: str


class LineNumberedData(BaseModel):
    type: Literal[DiffTypes.LINE_NUMBERED]
    # List of tuples (start_line, end_line, replacement_text)
    diff_chunks: List[Tuple[int, int, str]]


class SearchAndReplaceData(BaseModel):
    type: Literal[DiffTypes.SEARCH_AND_REPLACE]
    search_and_replace_blocks: str


DiffData = Annotated[Union[UdiffData, LineNumberedData,
                           SearchAndReplaceData], Field(discriminator="type")]


class FileDiffApplicationRequest(BaseModel):
    file_path: str
    repo_path: str
    current_content: str
    diff_data: DiffData


class FileDiffApplicationResponse(BaseModel):
    new_file_path: str
    new_content: str
