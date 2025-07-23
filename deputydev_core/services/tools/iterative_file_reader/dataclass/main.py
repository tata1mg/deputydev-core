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
