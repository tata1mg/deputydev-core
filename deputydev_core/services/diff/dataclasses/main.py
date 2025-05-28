from enum import Enum
from typing import Annotated, List, Literal, Tuple, Union

from pydantic import BaseModel, Field


class DiffTypes(str, Enum):
    UDIFF = "UDIFF"
    LINE_NUMBERED = "LINE_NUMBERED"


class UdiffData(BaseModel):
    type: Literal[DiffTypes.UDIFF]
    incremental_udiff: str


class LineNumberedData(BaseModel):
    type: Literal[DiffTypes.LINE_NUMBERED]
    diff_chunks: List[Tuple[int, int, str]]  # List of tuples (start_line, end_line, replacement_text)


DiffData = Annotated[Union[UdiffData, LineNumberedData], Field(discriminator="type")]


class FileDiffApplicationRequest(BaseModel):
    file_path: str
    repo_path: str
    current_content: str
    diff_data: DiffData


class FileDiffApplicationResponse(BaseModel):
    new_file_path: str
    new_content: str
