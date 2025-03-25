import os
from typing import Dict, List, Tuple

from deputydev_core.utils.app_logger import AppLogger


class LineNumberedDiffApplicator:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def _apply_diff_in_file_content(self, content: List[str], chunks: List[Tuple[int, int, str]]) -> List[str]:
        modified_content = []
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

    def get_final_content(self, diff: Dict[str, List[Tuple[int, int, str]]]) -> Dict[str, List[str]]:
        final_content: Dict[str, List[str]] = {}
        for fp, chunks in diff.items():
            # Sort the chunks by start line number to ensure proper processing order
            chunks = sorted(chunks, key=lambda x: x[0])
            abs_file_path = os.path.join(self.repo_path, fp)
            content = []
            # Attempt to read the file content, handling the case where the file doesn't exist
            try:
                with open(abs_file_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                    content = file_obj.readlines()
            except FileNotFoundError:
                AppLogger.log_info(f"File not found: {abs_file_path}, a new file will be created")

            # List to store the modified content
            modified_content = self._apply_diff_in_file_content(content=content, chunks=chunks)

            final_content[fp] = modified_content

        return final_content

    def apply_diff(self, diff: Dict[str, List[Tuple[int, int, str]]]):

        applied_content = self.get_final_content(diff)

        for fp, modified_content in applied_content.items():
            # Sort the chunks by start line number to ensure proper processing order
            # Write the modified content back to the file
            # if the file path does not exist, create the file path
            abs_file_path = os.path.join(self.repo_path, fp)
            if not os.path.exists(os.path.dirname(abs_file_path)):
                os.makedirs(os.path.dirname(abs_file_path))

            with open(abs_file_path, "w") as file_obj:
                file_obj.writelines(modified_content)
