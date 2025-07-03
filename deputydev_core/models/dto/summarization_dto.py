from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ContentType(Enum):
    CHUNK = "chunk"  # Regular file chunk
    SUMMARY = "summary"  # Summarized content


class SummarizationStrategy(Enum):
    """Strategy used for summarization"""

    AUTO = "auto"
    CODE = "code"
    TEXT = "text"
    SAMPLING = "sampling"


class FileType(Enum):
    """Type of file detected"""

    CODE = "code"
    TEXT = "text"
    CONFIG = "config"
    UNKNOWN = "unknown"


class SourceDetails(BaseModel):
    """Details about the source of the content"""

    file_path: str
    file_hash: Optional[str] = None
    start_line: int
    end_line: int


class LineRange(BaseModel):
    start_line: int
    end_line: int
    content_type: str
    construct_name: Optional[str] = None  # Name of function/class/etc
    description: Optional[str] = None


class FileSummaryResponse(BaseModel):
    """Response model for file summarization - kept for backward compatibility"""

    file_path: str
    file_type: FileType
    strategy_used: SummarizationStrategy
    summary_content: str
    model_config = ConfigDict(from_attributes=True)
