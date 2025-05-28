import asyncio
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails
from deputydev_core.services.repo.local_repo.local_repo_factory import LocalRepoFactory


class GrepSearch:
    """
    Class to grep files in directory.
    """

    def __init__(self, repo_path: str):
        """
        Initialize the GrepSearch with a directory path.

        :param repo_path: Path to the repository.
        :return: None
        """
        self.repo_path = repo_path

    async def perform_grep_search(
        self, directory_path: str, search_terms: List[str]
    ) -> List[Dict[str, Union[ChunkInfo, int]]]:
        """
        Perform a recursive grep search in the specified directory for multiple terms.

        :param directory_path: Path to the directory to be read.
        :param search_terms: A list of terms to search for in the files.
        :return: A list of GrepSearchResponse objects containing details of each match.
        """
        results: List[Dict[str, Union[ChunkInfo, int]]] = []
        abs_path = Path(os.path.join(self.repo_path, directory_path)).resolve()
        is_git_repo = LocalRepoFactory._is_git_repo(self.repo_path)
        if is_git_repo:
            command_template = 'git --git-dir="{repo_path}/.git" --work-tree="{repo_path}" grep -rnC 2 \'{search_term}\' -- {directory_path}'
        else:
            command_template = (
                "grep -rnC 2 '{search_term}' \"{abs_path}\" {exclude_flags}"
            )

        exclude_dirs = [
            "node_modules",
            "dist",
            "build",
            ".venv",
            ".git",
            "out",
            "venv",
            "__pycache__",
            "target",
            "bin",
            "obj",
            "vendor",
            "log",
            "tmp",
            "packages",
        ]
        exclude_flags = " ".join(f'--exclude-dir="{d}"' for d in exclude_dirs)

        for search_term in search_terms:
            command = command_template.format(
                search_term=search_term,
                directory_path=directory_path,
                repo_path=self.repo_path,
                exclude_flags=exclude_flags,
                abs_path=abs_path,
            )
            process = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if stdout:
                parsed_results = self.parse_lines(
                    stdout.decode().strip().splitlines(), is_git_repo
                )
                results.extend(parsed_results)

            if stderr:
                raise ValueError(stderr.decode().strip())

        return results[:100]

    def parse_lines(
        self, input_lines: List[str], is_git_repo: bool
    ) -> List[Dict[str, Union[ChunkInfo, int]]]:
        results: List[Dict[str, Union[ChunkInfo, int]]] = []
        chunk_lines: List[str] = []

        def process_chunk(
            chunk: List[str],
        ) -> Tuple[Optional[ChunkInfo], Optional[int]]:
            if not chunk:
                return None, None

            # Step 4: Find the exact match line (with `:` after line number)
            match_line = None
            file_path = None
            code_lines: List[str] = []

            for line in chunk:
                match = re.match(r"^(.*?):(\d+):(.*)$", line)
                if match:
                    file_path = match.group(1).strip()
                    match_line = int(match.group(2))
                    # code_lines.append(match.group(3).strip())
                    break

            if not file_path or match_line is None:
                return None, None

            # Step 2: Get all line numbers in the chunk (even context lines)
            line_numbers: List[int] = []
            for line in chunk:
                match_context = re.match(
                    rf"^{re.escape(file_path)}[-:](\d+)[-:]?(.*)$", line
                )
                if match_context:
                    line_num = int(match_context.group(1))
                    line_numbers.append(line_num)

            if not line_numbers:
                return None, None

            start_line: int = min(line_numbers)
            end_line: int = max(line_numbers)

            # Step 5 & 6: Remove file path and line numbers from all lines to get clean code
            for line in chunk:
                clean = re.sub(
                    rf"^{re.escape(file_path)}[-:](\d+)[-:]?", "", line
                ).strip()
                code_lines.append(clean)

            # Step 7: Join into a clean block of code
            chunk_text = "\n".join(code_lines)
            if not is_git_repo:
                # get relative path
                file_path = os.path.relpath(file_path, self.repo_path)

            return (
                ChunkInfo(
                    content=chunk_text,
                    source_details=ChunkSourceDetails(
                        file_path=file_path, start_line=start_line, end_line=end_line
                    ),
                ),
                match_line,
            )

        # Step 1: Split into chunks using '--'
        for line in input_lines:
            # process the current chunk if ending '--' is found
            if line.strip() == "--":
                chunk_info_obj, matched_line = process_chunk(chunk_lines)
                if chunk_info_obj and matched_line:
                    results.append(
                        {"chunk_info": chunk_info_obj, "matched_line": matched_line}
                    )
                chunk_lines = []

            # if line is not '--', add it to the current chunk
            else:
                chunk_lines.append(line)

        # Final chunk flush
        if chunk_lines:
            chunk_info_obj, matched_line = process_chunk(chunk_lines)
            if chunk_info_obj and matched_line:
                results.append(
                    {"chunk_info": chunk_info_obj, "matched_line": matched_line}
                )

        return results
