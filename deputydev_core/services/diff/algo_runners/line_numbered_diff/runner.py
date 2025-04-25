from typing import List, Tuple

from deputydev_core.services.diff.algo_runners.base_diff_algo_runner import (
    BaseDiffAlgoRunner,
)
from deputydev_core.services.diff.dataclasses.main import (
    FileDiffApplicationResponse,
    LineNumberedData,
)


class LineNumberedDiffAlgoRunner(BaseDiffAlgoRunner):
    @classmethod
    def _apply_diff_in_file_content(cls, content: List[str], chunks: List[Tuple[int, int, str]]) -> List[str]:
        modified_content: List[str] = []
        current_chunk_index = 0  # Tracks the current chunk being processed
        skip_line_upto = 0  # Tracks the lines to skip due to chunk processing

        # Process the file line by line
        for idx, line in enumerate(content):
            # Skip lines that are part of an already-applied chunk
            if idx < skip_line_upto:
                continue

            # If there are no remaining chunks, append the line as-is
            if current_chunk_index >= len(chunks):
                modified_content.append(line)
                continue

            line_number = idx + 1  # Convert zero-based index to line number

            # Check if the current line matches the start of the current chunk
            if chunks[current_chunk_index][0] == line_number:
                # Extract chunk details
                _, end_line, diff = chunks[current_chunk_index]
                diff_lines = diff.split("\n")  # Split diff content into lines

                # Add the diff content to the modified content
                modified_content.extend([line + "\n" for line in diff_lines])
                # remove the last newline character
                modified_content = modified_content[:-1]

                # Update the skip range and move to the next chunk
                skip_line_upto = end_line
                current_chunk_index += 1
            else:
                # If the current line is outside the chunk, append it as-is
                modified_content.append(line)

        # Handle any remaining chunks after processing the file lines
        for chunk in chunks[current_chunk_index:]:
            _, _, diff = chunk
            diff_lines = diff.split("\n")
            modified_content.extend([line + "\n" for line in diff_lines])

        return modified_content

    @classmethod
    async def apply_diff(
        cls, file_path: str, repo_path: str, current_content: str, diff_data: LineNumberedData
    ) -> FileDiffApplicationResponse:
        chunks = diff_data.diff_chunks
        # Sort the chunks by start line number to ensure proper processing order
        chunks = sorted(chunks, key=lambda x: x[0])
        content = current_content.splitlines(keepends=True)  # Split content into lines while preserving line endings
        # List to store the modified content
        modified_content = cls._apply_diff_in_file_content(content=content, chunks=chunks)
        return FileDiffApplicationResponse(
            new_file_path=file_path,
            new_content="".join(modified_content),
        )
