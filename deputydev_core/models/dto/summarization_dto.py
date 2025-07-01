from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict
from enum import Enum



class ContentType(Enum):
    CHUNK = "chunk"          # Regular file chunk
    SUMMARY = "summary"      # Summarized content


class SummarizationStrategy(Enum):
    """Strategy used for summarization"""
    AUTO = "auto"
    CODE = "code"
    TEXT = "text"
    SAMPLING = "sampling"


class FileType(str, Enum):
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



class FileContent(BaseModel):
    """
    Unified class for file content - can represent either regular chunks or summaries
    """
    # Core content fields
    content: str
    content_type: ContentType
    source_details: SourceDetails
    eof_reached: bool = False
    
    # Chunk-specific fields (only for CHUNK type)
    embedding: Optional[List[float]] = None
    search_score: Optional[float] = 0
    
    # Summary-specific fields (only for SUMMARY type)  
    file_type: Optional[FileType] = None
    strategy_used: Optional[SummarizationStrategy] = None
    total_lines: Optional[int] = None
    summary_lines: Optional[int] = None
    line_ranges: Optional[List[LineRange]] = None
    skipped_ranges: Optional[List[LineRange]] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def create_chunk(cls, content: str, file_path: str, start_line: int, end_line: int, 
                    file_hash: Optional[str] = None, eof_reached: bool = False) -> 'FileContent':
        """Create a regular chunk instance"""
        return cls(
            content=content,
            content_type=ContentType.CHUNK,
            source_details=SourceDetails(
                file_path=file_path,
                file_hash=file_hash,
                start_line=start_line,
                end_line=end_line
            ),
            eof_reached=eof_reached
        )
    
    @classmethod  
    def create_summary(cls, summary_content: str, file_path: str, file_type: FileType,
                      strategy_used: SummarizationStrategy, total_lines: int,
                      line_ranges: List[LineRange], skipped_ranges: List[LineRange],
                      eof_reached: bool = True) -> 'FileContent':
        """Create a summary instance"""
        return cls(
            content=summary_content,
            content_type=ContentType.SUMMARY,
            source_details=SourceDetails(
                file_path=file_path,
                start_line=1,
                end_line=total_lines
            ),
            eof_reached=eof_reached,
            file_type=file_type,
            strategy_used=strategy_used,
            total_lines=total_lines,
            summary_lines=len(summary_content.splitlines()) if summary_content else 0,
            line_ranges=line_ranges,
            skipped_ranges=skipped_ranges
        )
    
    def is_summary(self) -> bool:
        """Check if this content is a summary"""
        return self.content_type == ContentType.SUMMARY
    
    def is_chunk(self) -> bool:
        """Check if this content is a regular chunk"""
        return self.content_type == ContentType.CHUNK
    
    def get_content_with_lines(self, add_lines: bool = True) -> str:
        """Get content with optional line numbers"""
        if not add_lines:
            return self.content
            
        lines = self.content.split('\n')
        start_line = self.source_details.start_line
        
        formatted_lines = []
        for i, line in enumerate(lines):
            line_num = start_line + i
            formatted_lines.append(f"{line_num:4d}: {line}")
        
        return '\\n'.join(formatted_lines)


class FileSummaryResponse(BaseModel):
    """Response model for file summarization - kept for backward compatibility"""
    file_path: str
    file_type: FileType
    strategy_used: SummarizationStrategy
    total_lines: int
    summary_lines: int
    summary_content: str
    line_ranges: List[LineRange]
    skipped_ranges: List[LineRange]
    
    model_config = ConfigDict(from_attributes=True)