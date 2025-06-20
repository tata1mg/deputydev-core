import asyncio
import os
import re
from asyncio.subprocess import PIPE
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails
from deputydev_core.services.repo.local_repo.local_repo_factory import LocalRepoFactory


class GrepSearch:
    """
    Class to grep files in directory.
    """

    def __init__(self, repo_path: str) -> None:
        """
        Initialize the GrepSearch with a directory path.

        :param repo_path: Path to the repository.
        :return: None
        """
        self.repo_path = repo_path
        self.exclude_files = [
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
            "*.map",
        ]
        self.exclude_files += [
            "*.pyc",
            "*.class",
            "*.jar",
            "*.war",
            "*.o",
            "*.so",
            "*.dll",
            "*.exe",
            "*.min.js",
            "*.min.css",
            "*.bundle.js",
            "*~",
            "*.swp",
            "*.DS_Store",
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
            ".nyc_output.idea",
            "pip-wheel-metadata",
        ]

    def build_git_pathspec_exclusions_list(self) -> List[str]:
        """
        Build a list of git pathspec exclusion patterns for files and directories.
        :return: A list of git pathspec exclusion strings to be used with git commands.
        """
        exclusions: List[str] = []
        for dir_pattern in self.exclude_dirs:
            exclusions.append(f":(exclude){dir_pattern}")
            exclusions.append(f":(exclude){dir_pattern}/**")
        for file_pattern in self.exclude_files:
            exclusions.append(f":(exclude){file_pattern}")
            if "*" in file_pattern:
                exclusions.append(f":(exclude)**/{file_pattern}")
        return exclusions

    def build_git_command_args(
        self, search_term: str, directory_path: str, case_insensitive: bool, use_regex: bool
    ) -> List[str]:
        grep_flags = ["-rnC", "2"]
        grep_flags.append("-E" if use_regex else "-F")
        if case_insensitive:
            grep_flags.append("-i")

        return [
            "git",
            f"--git-dir={self.repo_path}/.git",
            f"--work-tree={self.repo_path}",
            "grep",
            *grep_flags,
            search_term,
            "--",
            directory_path,
            *self.build_git_pathspec_exclusions_list(),
        ]

    async def perform_grep_search(
        self, directory_path: str, search_term: str, case_insensitive: bool = False, use_regex: bool = False
    ) -> List[Dict[str, Union[ChunkInfo, int]]]:
        """
        Perform a recursive grep search in the specified directory.

        :param directory_path: Path to the directory to be read.
        :param search_term: A string or pattern to search for in the files.
        :return: A list of GrepSearchResponse objects containing details of each match.
        """
        results: List[Dict[str, Union[ChunkInfo, int]]] = []
        abs_path = Path(os.path.join(self.repo_path, directory_path)).resolve()  # noqa: PTH118
        is_git_repo = LocalRepoFactory.is_git_repo(self.repo_path)
        cwd = self.repo_path if os.path.isdir(self.repo_path) else "/"  # noqa: PTH112

        async def _run(command: List[str], is_git: bool) -> List[Dict[str, Union[ChunkInfo, int]]]:
            process = await asyncio.create_subprocess_exec(*command, stdout=PIPE, stderr=PIPE, cwd=cwd)
            stdout, stderr = await process.communicate()

            if process.returncode == 0 and stdout:
                return self.parse_lines(stdout.decode().strip().splitlines(), is_git)
            elif process.returncode == 1:
                return []
            else:
                raise RuntimeError(f"Grep failed: {stderr.decode().strip()}")

        if is_git_repo:
            # First try git grep
            command = self.build_git_command_args(search_term, directory_path, case_insensitive, use_regex)
            results = await _run(command, is_git=True)

            # If git grep finds nothing, fall back to regular grep
            if not results:
                command = self.build_grep_command(search_term, abs_path, case_insensitive, use_regex)
                results = await _run(command, is_git=False)

        else:
            # Only grep available
            command = self.build_grep_command(search_term, abs_path, case_insensitive, use_regex)
            results = await _run(command, is_git=False)

        if not results:
            raise ValueError(f"No matches found for '{search_term}' in {directory_path}.")

        return results[:50]

    def build_grep_command(
        self,
        search_term: str,
        abs_path: Path,
        case_insensitive: bool,
        use_regex: bool,
    ) -> List[str]:
        """
        Build regular grep command with exclusions.

        :param search_term: Term to search for.
        :param abs_path: Absolute path to search in.
        :param case_insensitive: If true, performs a case-insensitive search.
        :param use_regex: If true, treats the search term as a regular expression.
        :return: Complete grep command string.
        """
        grep_flags = ["-rnC", "2"]
        grep_flags.append("-E" if use_regex else "-F")
        if case_insensitive:
            grep_flags.append("-i")

        command = ["grep", *grep_flags, search_term, str(abs_path)]
        command += [f"--exclude-dir={d}" for d in self.exclude_dirs]
        command += [f"--exclude={f}" for f in self.exclude_files]

        return command

    def parse_lines(self, input_lines: List[str], is_git_repo: bool) -> List[Dict[str, Union[ChunkInfo, int]]]:  # noqa : C901
        results: List[Dict[str, Union[ChunkInfo, int]]] = []
        chunk_lines: List[str] = []

        def process_chunk(  # noqa: C901
            chunk: List[str],
        ) -> Tuple[Optional[ChunkInfo], Optional[int]]:
            if not chunk:
                return None, None

            # Step 4: Find the exact match line (with `:` after line number)
            match_line = None
            file_path = None
            code_lines: List[str] = []
            # max visible chars per line before we clip
            MAX_LEN = 200  # noqa: N806

            for line in chunk:
                match = re.match(r"^(.*?):(\d+):(.*)$", line)
                if match:
                    file_path = match.group(1).strip()
                    match_line = int(match.group(2))
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

            # Step 5 & 6: Clean up lines and truncate if necessary
            for line in chunk:
                clean = re.sub(rf"^{re.escape(file_path)}[-:](\d+)[-:]?", "", line).rstrip()

                if len(clean) > MAX_LEN:
                    orig_len = len(clean)
                    half = MAX_LEN // 2 - 3
                    head = clean[:half]
                    tail = clean[-half:]
                    clean = f"{head} … {tail} (truncated, {orig_len} chars)"

                code_lines.append(clean)

            # Step 7: Join into a clean block of code
            chunk_text = "\n".join(code_lines)
            if not is_git_repo:
                # get relative path
                file_path = Path(file_path).relative_to(self.repo_path).as_posix()

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
