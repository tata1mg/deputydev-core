from pathlib import Path
from typing import Optional, Tuple

import aiofiles

from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails
from deputydev_core.services.file_summarization.file_summarization_service import FileSummarizationService
from deputydev_core.services.tools.iterative_file_reader.dataclass.main import (
    IterativeFileReaderResponse,
)
from deputydev_core.utils.app_logger import AppLogger


class IterativeFileReader:
    """
    Read files iteratively with optional summarization when requesting the whole file.
    Returns an IterativeFileReaderResponse: { chunk, eof, was_summary, total_lines }.
    """

    def __init__(self, file_path: str, repo_path: str, max_requested_line_range: Optional[int] = None) -> None:
        """
        :param file_path: Path to the file to be read (relative to repo_path).
        :param repo_path: Root path of the repository (for summarization + IO).
        :param max_requested_line_range: Maximum number of lines to read at once (default 1000).
        """
        self.file_path = file_path
        self.repo_path = repo_path
        self.max_requested_line_range: int = max_requested_line_range or 1000

    async def count_total_lines(self) -> int:
        """
        Count total lines in the file efficiently with encoding fallback.
        """
        full_path = Path(self.repo_path) / self.file_path
        try:
            # Try UTF-8 first
            try:
                async with aiofiles.open(full_path, mode="r", encoding="utf-8") as file:
                    line_count = 0
                    async for _ in file:
                        line_count += 1
                    return line_count
            except UnicodeDecodeError:
                # Fall back to latin-1
                async with aiofiles.open(full_path, mode="r", encoding="latin-1") as file:
                    line_count = 0
                    async for _ in file:
                        line_count += 1
                    return line_count
        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(f"Error counting lines in {full_path}: {str(e)}")
            return 0

    async def give_summary(self, start_line: int, end_line: int, total_lines: int) -> IterativeFileReaderResponse:
        """
        Attempt to summarize the file. On failure, fall back to a raw chunk read.
        Always returns the standard result dict.
        """
        full_path = Path(self.repo_path) / self.file_path
        try:
            summary_response = await FileSummarizationService.summarize_file(
                self.file_path, self.repo_path, max_lines=200, include_line_numbers=True
            )

            summary_source = ChunkSourceDetails(file_path=str(full_path), start_line=start_line, end_line=end_line)
            summary_chunk = ChunkInfo(
                content=summary_response.summary_content,
                source_details=summary_source,
            )
            # For summary of entire file, consider it a terminal response (eof=True).
            return IterativeFileReaderResponse(
                chunk=summary_chunk,
                eof=True,
                was_summary=True,
                total_lines=total_lines,
            )
        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(f"Summarization failed for {full_path}, falling back to regular reading: {str(e)}")
            # Fall back: read the first allowed window as raw content
            return await self._read_raw_chunk(
                start_line=start_line,
                end_line=min(start_line + self.max_requested_line_range - 1, end_line),
                total_lines=total_lines,
            )

    async def _read_raw_chunk(self, start_line: int, end_line: int, total_lines: int) -> IterativeFileReaderResponse:
        """
        Read raw lines between [start_line, end_line], inclusive, with encoding fallback.
        Returns the standard result dict.
        """
        full_path = Path(self.repo_path) / self.file_path

        async def _read_with_encoding(encoding: str) -> Tuple[ChunkInfo, bool]:
            async with aiofiles.open(full_path, mode="r", encoding=encoding) as file:
                # Move to start_line (1-indexed)
                for line_iterator in range(start_line - 1):
                    line = await file.readline()
                    if not line:
                        # EOF before start_line
                        chunk_details = ChunkSourceDetails(
                            file_path=str(full_path),
                            start_line=line_iterator + 1,
                            end_line=line_iterator + 1,
                        )
                        return ChunkInfo(content="", source_details=chunk_details), True

                file_content: str = ""
                actual_line_end: int = start_line
                eof_reached: bool = False

                max_to_read = min(self.max_requested_line_range, end_line - start_line + 1)
                for line_idx in range(max_to_read):
                    line = await file.readline()
                    if not line:
                        eof_reached = True
                        break
                    actual_line_end = start_line + line_idx
                    file_content += line

                if actual_line_end >= total_lines:
                    eof_reached = True

                chunk_details = ChunkSourceDetails(
                    file_path=str(full_path),
                    start_line=start_line,
                    end_line=actual_line_end,
                )
                return ChunkInfo(content=file_content, source_details=chunk_details), eof_reached

        try:
            chunk, eof_reached = await _read_with_encoding("utf-8")
        except UnicodeDecodeError:
            chunk, eof_reached = await _read_with_encoding("latin-1")
        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(f"Error reading {full_path}: {str(e)}")
            # Return a safe empty payload on error
            empty_details = ChunkSourceDetails(file_path=str(full_path), start_line=start_line, end_line=start_line)
            empty_chunk = ChunkInfo(content="", source_details=empty_details)

            return IterativeFileReaderResponse(
                chunk=empty_chunk,
                eof=True,
                was_summary=False,
                total_lines=total_lines,
            )

        return IterativeFileReaderResponse(
            chunk=chunk,
            eof=eof_reached,
            was_summary=False,
            total_lines=total_lines,
        )

    async def read_lines(
        self, start_line: Optional[int] = None, end_line: Optional[int] = None
    ) -> IterativeFileReaderResponse:
        """
        Read a chunk of lines. If the whole file is requested and exceeds the limit,
        return a summary instead.

        :param start_line: 1-indexed start line to read from. Defaults to 1.
        :param end_line: 1-indexed end line (inclusive). Defaults to total file lines.
        :return: IterativeFileReaderResponse with keys: chunk (ChunkInfo), eof (bool), was_summary (bool), total_lines (int)
        """
        total_lines: int = await self.count_total_lines()

        if total_lines <= 0:
            full_path = Path(self.repo_path) / self.file_path
            details = ChunkSourceDetails(file_path=str(full_path), start_line=1, end_line=1)
            return IterativeFileReaderResponse(
                chunk=ChunkInfo(content="", source_details=details),
                eof=True,
                was_summary=False,
                total_lines=0,
            )

        start_line_to_use: int = start_line or 1
        end_line_to_use: int = end_line or total_lines

        # Guard: invalid range
        if end_line_to_use < start_line_to_use:
            full_path = Path(self.repo_path) / self.file_path
            details = ChunkSourceDetails(
                file_path=str(full_path), start_line=start_line_to_use, end_line=start_line_to_use
            )
            return IterativeFileReaderResponse(
                chunk=ChunkInfo(content="", source_details=details),
                eof=True,
                was_summary=False,
                total_lines=total_lines,
            )

        # If caller asks for "entire file" (both None) and it's big, give a summary
        if start_line is None and end_line is None:
            requested_span = (
                end_line_to_use - start_line_to_use + 1
            )  # equals total_lines here; kept for future flexibility
            if requested_span > self.max_requested_line_range:
                return await self.give_summary(
                    start_line=start_line_to_use,
                    end_line=end_line_to_use,
                    total_lines=total_lines,
                )

        # Otherwise do a regular chunked read (within max_requested_line_range)
        end_line_capped = min(end_line_to_use, start_line_to_use + self.max_requested_line_range - 1)
        return await self._read_raw_chunk(
            start_line=start_line_to_use,
            end_line=end_line_capped,
            total_lines=total_lines,
        )
