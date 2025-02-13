import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from sanic.log import logger
from xxhash import xxh64

from common.services.chunking.config.chunk_config import ChunkConfig
from common.utils.app_logger import AppLogger


class BaseLocalRepo(ABC):
    def __init__(self, repo_path: str, chunk_config: Optional[ChunkConfig] = None):
        self.repo_path = repo_path
        self.chunk_config = chunk_config or ChunkConfig()

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

    def apply_diff(self, diff: Dict[str, List[Tuple[int, int, str]]]):
        for fp, chunks in diff.items():
            # Sort the chunks by start line number to ensure proper processing order
            chunks = sorted(chunks, key=lambda x: x[0])
            abs_file_path = os.path.join(self.repo_path, fp)
            content = []
            # Attempt to read the file content, handling the case where the file doesn't exist
            try:
                with open(abs_file_path, "r") as file_obj:
                    content = file_obj.readlines()
            except FileNotFoundError:
                logger.info(f"File not found: {abs_file_path}, a new file will be created")

            # List to store the modified content
            modified_content = self._apply_diff_in_file_content(content=content, chunks=chunks)

            # Write the modified content back to the file
            # if the file path does not exist, create the file path
            if not os.path.exists(os.path.dirname(abs_file_path)):
                os.makedirs(os.path.dirname(abs_file_path))

            with open(abs_file_path, "w") as file_obj:
                file_obj.writelines(modified_content)

    def _get_file_hash(self, file_path: str) -> str:
        with open(os.path.join(self.repo_path, file_path), "rb") as file:
            file_content = file.read()
            return xxh64(file_content).hexdigest()

    def _is_file_chunkable(self, file_path: str) -> bool:
        try:
            abs_file_path = os.path.join(self.repo_path, file_path)
            file_ext = os.path.splitext(abs_file_path)[1]
            if file_ext.lower() in self.chunk_config.exclude_exts:
                return False
            if not os.path.isfile(abs_file_path):
                return False
            if os.path.getsize(abs_file_path) > self.chunk_config.max_chunkable_file_size_bytes:
                AppLogger.log_debug(f"File size is greater than the max_chunkable_file_size_bytes: {abs_file_path}")
                return False
            # check if the filepath startswith any of the exclude_dirs
            if any(
                    abs_file_path.startswith(os.path.join(self.repo_path, exclude_dir))
                    for exclude_dir in self.chunk_config.exclude_dirs
            ):
                return False
            return True
        except Exception as ex:
            AppLogger.log_debug(f"Error while checking if file is chunkable: {ex} for file: {file_path}")
            return False

    @abstractmethod
    async def get_chunkable_files_and_commit_hashes(self) -> Dict[str, str]:
        raise NotImplementedError("get_file_to_commit_hash_map method must be implemented in the child class")

    @abstractmethod
    async def get_chunkable_files(self) -> List[str]:
        raise NotImplementedError("get_chunkable_files method must be implemented in the child class")
