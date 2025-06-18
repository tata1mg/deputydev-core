import asyncio
import shlex
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
        self.exclude_files = [
            "pyproject.toml",
            "package-lock.json",
            "yarn.lock",
            "*.log",
            "*.tmp",
            "*.cache",
            "*.lock",
            "package-lock.json",
            "*.pem",
            ".env",
            "*.zip",
            "*.tar",
            "*.rar",
            "bun.lockb",
        ]
        self.exclude_dirs = [
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
            ".pytest_cache",
            ".tox",
            "coverage",
            ".nyc_output"
        ]

    def build_git_pathspec_exclusions(self) -> str:
        """
        Build Git pathspec exclusions for directories and files.

        :return: String of pathspec exclusions for git grep.
        """
        exclusions = []

        for dir_pattern in self.exclude_dirs:
            exclusions.append(f":(exclude){dir_pattern}")
            exclusions.append(f":(exclude){dir_pattern}/**")

        # Exclude specific files
        for file_pattern in self.exclude_files:
            exclusions.append(f":(exclude){file_pattern}")
            if '*' in file_pattern:
                exclusions.append(f":(exclude)**/{file_pattern}")

        return " ".join(f'"{exc}"' for exc in exclusions)


    def build_grep_exclusions(self) -> Tuple[str, str]:
        """
        Build exclusion flags for regular grep command.

        :return: Tuple of (exclude_dir_flags, exclude_file_flags).
        """
        exclude_dir_flags = " ".join(f'--exclude-dir="{d}"' for d in self.exclude_dirs)
        exclude_file_flags = " ".join(f'--exclude="{f}"' for f in self.exclude_files)
        return exclude_dir_flags, exclude_file_flags

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
        is_git_repo = LocalRepoFactory.is_git_repo(self.repo_path)

        for search_term in search_terms:

            if is_git_repo:
                command = self.build_git_command(search_term, directory_path)
            else:
                command = self.build_grep_command(search_term, abs_path)

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.repo_path or "/"
            )
            stdout, stderr = await process.communicate()

            if stdout:
                parsed_results = self.parse_lines(stdout.decode().strip().splitlines(), is_git_repo)
                results.extend(parsed_results)

            if stderr:
                raise ValueError(stderr.decode().strip())


        return results[:100]

    def build_git_command(self, search_term: str, directory_path: str) -> str:
        """
        Build git grep command with proper exclusions.

        :param search_term: Term to search for.
        :param directory_path: Directory path to search in.
        :return: Complete git grep command string.
        """
        escaped_term = self.shell_escape(search_term)

        command = (
            f'git --git-dir="{self.repo_path}/.git" --work-tree="{self.repo_path}" '
            f'grep -rnF -C 2 {escaped_term} '
            f'-- "{directory_path}" {self.build_git_pathspec_exclusions()}'
        )

        return command

    def build_grep_command(self, search_term: str, abs_path: Path) -> str:
        """
        Build regular grep command with exclusions.

        :param search_term: Term to search for.
        :param abs_path: Absolute path to search in.
        :return: Complete grep command string.
        """
        escaped_term = self.shell_escape(search_term)
        exclude_dir_flags, exclude_file_flags = self.build_grep_exclusions()

        command = (
            f'grep -rnF -C 2 {escaped_term} "{abs_path}" '
            f'{exclude_dir_flags} {exclude_file_flags}'
        )

        return command
    
    def shell_escape(self, s: str) -> str:
        """Escape double quotes in a string so it is safe to use in shell double-quoted strings.

        Args:
            s (str): The input string to escape.

        Returns:
            str: The escaped string, suitable for use in shell commands inside double quotes.
        """
        return shlex.quote(s)



    def parse_lines(self, input_lines: List[str], is_git_repo: bool) -> List[Dict[str, Union[ChunkInfo, int]]]:
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
                match_context = re.match(rf"^{re.escape(file_path)}[-:](\d+)[-:]?(.*)$", line)
                if match_context:
                    line_num = int(match_context.group(1))
                    line_numbers.append(line_num)

            if not line_numbers:
                return None, None

            start_line: int = min(line_numbers)
            end_line: int = max(line_numbers)

            # Step 5 & 6: Remove file path and line numbers from all lines to get clean code
            for line in chunk:
                clean = re.sub(rf"^{re.escape(file_path)}[-:](\d+)[-:]?", "", line).strip()
                code_lines.append(clean)

            # Step 7: Join into a clean block of code
            chunk_text = "\n".join(code_lines)
            if not is_git_repo:
                # get relative path
                file_path = os.path.relpath(file_path, self.repo_path)

            return (
                ChunkInfo(
                    content=chunk_text,
                    source_details=ChunkSourceDetails(file_path=file_path, start_line=start_line, end_line=end_line),
                ),
                match_line,
            )

        # Step 1: Split into chunks using '--'
        for line in input_lines:
            # process the current chunk if ending '--' is found
            if line.strip() == "--":
                chunk_info_obj, matched_line = process_chunk(chunk_lines)
                if chunk_info_obj and matched_line:
                    results.append({"chunk_info": chunk_info_obj, "matched_line": matched_line})
                chunk_lines = []

            # if line is not '--', add it to the current chunk
            else:
                chunk_lines.append(line)

        # Final chunk flush
        if chunk_lines:
            chunk_info_obj, matched_line = process_chunk(chunk_lines)
            if chunk_info_obj and matched_line:
                results.append({"chunk_info": chunk_info_obj, "matched_line": matched_line})

        return results
