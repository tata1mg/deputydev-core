
import os
from pathlib import Path
from typing import Optional, Tuple

import aiofiles

from deputydev_core.models.dto.summarization_dto import FileContent
from deputydev_core.services.file_summarization.file_summarization_service import \
    FileSummarizationService
from deputydev_core.utils.app_logger import AppLogger


class IterativeFileReader:
    """
    Enhanced class to read files in an iterative manner with summarization support.
    Automatically summarizes large files when reading the entire content.
    """

    def __init__(self, file_path: str, max_lines: Optional[int] = None, repo_path: Optional[str] = None)->None:
        """
        Initialize the IterativeFileReader with a file path.

        :param file_path: Path to the file to be read.
        :param max_lines: Maximum number of lines to read at once.
        :param repo_path: Root path of the repository (for summarization).
        :return: None
        """
        self.file_path = file_path
        self.max_lines: int = max_lines or 100
        self.repo_path = repo_path
        path=Path(file_path)
        # If repo_path not provided, try to extract it from file_path
        if not self.repo_path:
            self.repo_path = str(path.parent) if path.parent else "."

    async def read_lines(self, start_line: int, end_line: int) -> Tuple[FileContent, bool]:
        """
        Read a chunk of lines from the file starting from the given offset.
        If reading the entire file and it's >1000 lines, returns a summary instead.
        
        :param start_line: The line number to start reading from.
        :param end_line: The line number to stop reading at.
        :return: Tuple of (FileContent, eof_reached)

        Reads the file asynchronously in chunks of max_lines.
        """

        if start_line < 1 or end_line < 1 or end_line < start_line:
            raise ValueError("Invalid start_line or end_line")
        path=Path(self.file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        # Check if we should summarize large files
        total_lines = await self._count_total_lines()
        
        if FileSummarizationService.should_summarize(total_lines, start_line, end_line):
            try:
                relative_path = os.path.relpath(self.file_path, self.repo_path) if self.repo_path else self.file_path
                summary_response = await FileSummarizationService.summarize_file(
                    relative_path, self.repo_path or "", max_lines=200, include_line_numbers=True
                )
                
                # Convert FileSummaryResponse to FileContent
                summary_content = FileContent.create_summary(
                    summary_content=summary_response.summary_content,
                    file_path=summary_response.file_path,
                    file_type=summary_response.file_type,
                    strategy_used=summary_response.strategy_used,
                    total_lines=summary_response.total_lines,
                    line_ranges=summary_response.line_ranges,
                    skipped_ranges=summary_response.skipped_ranges,
                    eof_reached=True
                )
                return summary_content, True
            except Exception as e:
                AppLogger.log_error(f"Summarization failed for {self.file_path}, falling back to regular reading: {str(e)}")
                # Fall back to regular reading if summarization fails
                pass

        # Regular iterative reading
        async with aiofiles.open(self.file_path, mode="r", encoding="utf-8") as file:
            # Move the file pointer to the start_line
            for line_iterator in range(start_line - 1):  # 1 indexed
                line = await file.readline()
                if not line:
                    # End of file reached
                    return (
                        FileContent.create_chunk(
                            content="",
                            file_path=self.file_path,
                            start_line=line_iterator + 1,
                            end_line=line_iterator + 1,
                            eof_reached=True
                        ),
                        True,
                    )

            file_content: str = ""
            # Read the next min(max_lines, end_line - start_line) lines or until the end of the file

            actual_line_end: int = start_line

            eof_reached: bool = False
            for line_iterator in range(min(self.max_lines, end_line - start_line + 1)):  # 1 indexed
                line = await file.readline()
                if not line:
                    # End of file reached
                    eof_reached = True
                    break
                actual_line_end = start_line + line_iterator
                file_content += line

            return (
                FileContent.create_chunk(
                    content=file_content,
                    file_path=self.file_path,
                    start_line=start_line,
                    end_line=actual_line_end,
                    eof_reached=eof_reached
                ),
                eof_reached,
            )
    
    async def _count_total_lines(self) -> int:
        """
        Count total lines in the file efficiently.
        """
        try:
        # Try first with utf-8
            try:
                async with aiofiles.open(self.file_path, mode="r", encoding="utf-8") as file:
                    line_count = 0
                    async for _ in file:
                        line_count += 1
                    return line_count
            except UnicodeDecodeError:
                # Fall back to latin-1
                async with aiofiles.open(self.file_path, mode="r", encoding="latin-1") as file:
                    line_count = 0
                    async for _ in file:
                        line_count += 1
                    return line_count
        except Exception as e:
            # Log the specific error
            AppLogger.log_error(f"Error counting lines in {self.file_path}: {str(e)}")
            return 0
