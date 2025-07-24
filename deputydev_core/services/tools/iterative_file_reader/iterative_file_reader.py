from pathlib import Path
from typing import Optional, Tuple

import aiofiles

from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails
from deputydev_core.services.file_summarization.file_summarization_service import FileSummarizationService
from deputydev_core.utils.app_logger import AppLogger


class IterativeFileReader:
    """
    Enhanced class to read files in an iterative manner with summarization support.
    Automatically summarizes large files when reading the entire content.
    """

    def __init__(self, file_path: str, repo_path: str, max_requested_line_range: Optional[int] = None) -> None:
        """
        Initialize the IterativeFileReader with a file path.

        :param file_path: Path to the file to be read.
        :param max_lines: Maximum number of lines to read at once.
        :param repo_path: Root path of the repository (for summarization).
        :return: None
        """
        self.file_path = file_path
        self.repo_path = repo_path
        self.max_requested_line_range: int = max_requested_line_range or 1000

    async def count_total_lines(self) -> int:
        """
        Count total lines in the file efficiently.
        """
        try:
            # Try first with utf-8
            try:
                async with aiofiles.open(Path(self.repo_path) / self.file_path, mode="r", encoding="utf-8") as file:
                    line_count = 0
                    async for _ in file:
                        line_count += 1
                    return line_count
            except UnicodeDecodeError:
                # Fall back to latin-1
                async with aiofiles.open(Path(self.repo_path) / self.file_path, mode="r", encoding="latin-1") as file:
                    line_count = 0
                    async for _ in file:
                        line_count += 1
                    return line_count
        except Exception as e:  # noqa: BLE001
            # Log the specific error
            AppLogger.log_error(f"Error counting lines in {Path(self.repo_path) / self.file_path}: {str(e)}")
            return 0

    async def give_summary(self, start_line: int, end_line: int) -> Tuple[ChunkInfo, bool]:
        try:
            summary_response = await FileSummarizationService.summarize_file(
                self.file_path, self.repo_path, max_lines=200, include_line_numbers=True
            )

            summary_source = ChunkSourceDetails(
                file_path=str(Path(self.repo_path) / self.file_path), start_line=start_line, end_line=end_line
            )
            summary_content = ChunkInfo(
                content=summary_response.summary_content,
                source_details=summary_source,
            )
            return summary_content, True
        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(
                f"Summarization failed for {Path(self.repo_path) / self.file_path}, falling back to regular reading: {str(e)}"
            )
            pass

    async def read_lines(
        self, start_line: Optional[int] = None, end_line: Optional[int] = None
    ) -> Tuple[ChunkInfo, bool]:
        """
        Read a chunk of lines from the file starting from the given offset.
        If reading the entire file and it's >1000 lines, returns a summary instead.

        :param start_line: The line number to start reading from.
        :param end_line: The line number to stop reading at.
        :return: Tuple of (ChunkInfo, eof_reached)

        Reads the file asynchronously in chunks of max_lines.
        """

        # TODO: Add a better logic to count lines
        start_line_to_use: int = start_line or 1
        end_line_to_use: int = end_line or await self.count_total_lines()

        if (
            start_line is None
            and end_line is None
            and (end_line_to_use - start_line_to_use + 1) > self.max_requested_line_range
        ):
            return await self.give_summary(start_line=start_line_to_use, end_line=end_line_to_use)

        # Regular iterative reading
        async with aiofiles.open(Path(self.repo_path) / self.file_path, mode="r", encoding="utf-8") as file:
            # Move the file pointer to the start_line
            for line_iterator in range(start_line_to_use - 1):  # 1 indexed
                line = await file.readline()
                if not line:
                    # End of file reached
                    chunk_details = ChunkSourceDetails(
                        file_path=str(Path(self.repo_path) / self.file_path),
                        start_line=line_iterator + 1,
                        end_line=line_iterator + 1,
                    )
                    return (
                        ChunkInfo(content="", source_details=chunk_details),
                        True,
                    )

            file_content: str = ""
            # Read the next min(max_lines, end_line - start_line) lines or until the end of the file

            actual_line_end: int = start_line_to_use

            eof_reached: bool = False
            for line_iterator in range(
                min(self.max_requested_line_range, end_line_to_use - start_line_to_use + 1)
            ):  # 1 indexed
                line = await file.readline()
                if not line:
                    # End of file reached
                    eof_reached = True
                    break
                actual_line_end = start_line_to_use + line_iterator
                file_content += line
            chunk_details = ChunkSourceDetails(
                file_path=str(Path(self.repo_path) / self.file_path),
                start_line=start_line_to_use,
                end_line=actual_line_end,
            )
            return (
                ChunkInfo(content=file_content, source_details=chunk_details),
                eof_reached,
            )
