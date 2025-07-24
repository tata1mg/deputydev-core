from typing import Any, Optional

from pydantic import BaseModel, field_validator


class IterativeFileReaderRequestParams(BaseModel):
    """
    Request parameters for the IterativeFileReader.
    """

    file_path: str
    repo_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    @field_validator("start_line", "end_line")
    @classmethod
    def keep_positive_or_null_startlines(cls, v: Any, info: Any) -> Optional[int]:
        if v is not None and isinstance(v, int) and v >= 1:
            return v
        return None


class FileSummaryReaderRequestParams(BaseModel):
    """
    Request parameters for the FileSummaryReader.
    """

    file_path: str
    repo_path: Optional[str] = None
    number_of_lines: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    @field_validator("start_line", "end_line", "number_of_lines")
    @classmethod
    def check_positive(cls, v: Any, info: Any) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError(f"{info.field_name} must be a positive integer")
        return v
