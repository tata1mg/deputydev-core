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
    def check_positive(cls, v: Any, info: Any) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError(f"{info.field_name} must be a positive integer")

        return v
