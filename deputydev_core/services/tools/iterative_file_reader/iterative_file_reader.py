from typing import Optional, Tuple

import aiofiles

from deputydev_core.errors.tools.tool_errors import InvalidToolParamsError
from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails


class IterativeFileReader:
    """
    Class to read files in an iterative manner.
    """

    def __init__(self, file_path: str, max_lines: Optional[int] = None) -> None:
        """
        Initialize the IterativeFileReader with a file path.

        :param file_path: Path to the file to be read.
        :param max_lines: Maximum number of lines to read at once.
        :return: None
        """
        self.file_path = file_path
        self.max_lines: int = max_lines or 100

    async def read_lines(self, start_line: int, end_line: int) -> Tuple[ChunkInfo, bool]:
        """
        Read a chunk of lines from the file starting from the given offset.
        :param start_line: The line number to start reading from.
        :param end_line: The line number to stop reading at.
        :return: A string containing the read lines.

        Reads the file asynchronously in chunks of max_lines.
        """

        if start_line < 1 or end_line < 1 or end_line < start_line:
            raise InvalidToolParamsError("Invalid start_line or end_line")

        try:
            async with aiofiles.open(self.file_path, mode="r", encoding="utf-8") as file:  # type: ignore
                # Move the file pointer to the start_line
                for line_iterator in range(start_line - 1):  # 1 indexed
                    line = await file.readline()
                    if not line:
                        # End of file reached
                        return (
                            ChunkInfo(
                                content="",
                                embedding=None,
                                source_details=ChunkSourceDetails(
                                    file_path=self.file_path,
                                    start_line=line_iterator + 1,
                                    end_line=line_iterator + 1,
                                ),
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
                    ChunkInfo(
                        content=file_content,
                        embedding=None,
                        source_details=ChunkSourceDetails(
                            file_path=self.file_path,
                            start_line=start_line,
                            end_line=actual_line_end,
                        ),
                    ),
                    eof_reached,
                )
        except FileNotFoundError:
            raise InvalidToolParamsError(f"File not found: {self.file_path}")
