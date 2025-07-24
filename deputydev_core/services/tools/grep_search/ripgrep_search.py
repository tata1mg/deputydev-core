import asyncio
import json
import re
from asyncio.subprocess import PIPE
from pathlib import Path
from typing import Dict, List, Optional, Union

from deputydev_core.errors.tools.tool_errors import EmptyToolResponseError, UnhandledToolError
from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails

# If you keep get_rg_path() in another module, just import it instead.


class GrepSearch:
    """
    Fast recursive code-search powered by ripgrep.
    """

    def __init__(self, repo_path: str, ripgrep_path: str) -> None:
        """
        :param repo_path: Path to the repository root (searched relative to this path).
        :param ripgrep_path: Optional explicit path to the rg binary. Defaults to get_rg_path().
        """
        self.repo_path = Path(repo_path).resolve()
        self.ripgrep_path = ripgrep_path

        # Same exclude lists you had before; now converted to --glob patterns.
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
        self.exclusion_args = self._build_rg_exclusion_globs()

    # ---------------------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------------------

    async def perform_grep_search(
        self,
        directory_path: str,
        search_term: str,
        case_insensitive: bool = False,
        use_regex: bool = False,
    ) -> List[Dict[str, Union[ChunkInfo, int]]]:
        """
        Search `directory_path` (relative to repo root) for `search_term`.

        :returns: List of dicts  [{"chunk_info": ChunkInfo, "matched_line": int}, …]
        """
        abs_path = (self.repo_path / directory_path).resolve()
        # Ensure the abs_path is INSIDE the repo root
        try:
            rel_path = abs_path.relative_to(self.repo_path)
        except ValueError:
            raise UnhandledToolError(f"directory_path '{directory_path}' is outside the repo root '{self.repo_path}'")
        rel_path = str(Path(directory_path).as_posix()).strip() or "."
        command = self._build_rg_command(
            search_term=search_term,
            rel_path=rel_path,
            case_insensitive=case_insensitive,
            use_regex=use_regex,
        )

        results = await self._run_rg(command)

        if not results:
            raise EmptyToolResponseError(f"No matches found for '{search_term}' in {directory_path}.")

        # Cap to 50 chunks (keeps downstream model happy)
        return results[:50]

    # ---------------------------------------------------------------------
    # INTERNAL HELPERS
    # ---------------------------------------------------------------------

    # _build_rg_command  ──► ADD --json  +  --path-separator /
    def _build_rg_command(
        self,
        search_term: str,
        rel_path: str,
        case_insensitive: bool,
        use_regex: bool,
    ) -> List[str]:
        cmd: List[str] = [
            self.ripgrep_path,
            "--json",  # <── JSON EVENTS
            "--path-separator",
            "/",  # <── ensures forward-slash + relative paths
            "-n",  # line numbers
            "-C",
            "2",  # 2 context lines
            "--max-filesize",
            "200K",  # limit to 2KB files
        ]

        if not use_regex:
            cmd.append("-F")
        if case_insensitive:
            cmd.append("-i")

        cmd.extend(self.exclusion_args)

        # pattern then path
        cmd.append(search_term)
        cmd.append(rel_path)

        return cmd

    def _build_rg_exclusion_globs(self) -> List[str]:
        """
        Convert exclude lists to ripgrep --glob patterns.
        """
        globs: List[str] = []
        for d in self.exclude_dirs:
            globs.extend(["--glob", f"!{d}/**"])
        for f in self.exclude_files:
            globs.extend(["--glob", f"!{f}"])
        return globs

    # _run_rg  ──► route stdout to new JSON parser
    async def _run_rg(self, command: List[str]) -> List[Dict[str, Union[ChunkInfo, int]]]:
        process = await asyncio.create_subprocess_exec(*command, stdout=PIPE, stderr=PIPE, cwd=str(self.repo_path))
        stdout, stderr = await process.communicate()

        if process.returncode == 0 and stdout:
            return self._parse_json_stream(stdout.decode().splitlines())
        elif process.returncode == 1:
            return []
        else:
            raise UnhandledToolError(f"ripgrep failed (code {process.returncode}): {stderr.decode().strip()}")

    # ---------------------------------------------------------------------
    # OUTPUT PARSING (optimized for performance and clarity)
    # ---------------------------------------------------------------------
    def _parse_json_stream(self, json_lines: List[str]) -> List[Dict[str, Union[ChunkInfo, int]]]:  # noqa: C901
        """
        Consume ripgrep --json output and return our old structure:
        [{"chunk_info": ChunkInfo, "matched_line": int}, ...]
        - Groups adjacent matches/context lines into 'chunks'
        - Truncates long lines for output safety
        - Strips 'path:ln:' prefixes for cleaner display
        """
        results: List[Dict[str, Union[ChunkInfo, int]]] = []

        chunk_lines: List[str] = []  # Raw grep-style lines in this chunk
        line_numbers: List[int] = []  # All line numbers (context + matches)
        current_path: Optional[str] = None  # File currently being chunked
        match_line_num: Optional[int] = None  # The line number of the match
        prefix_regex: Optional[re.Pattern[str]] = None  # Cached regex for prefix
        MAX_LEN = 200  # Line truncation limit  # noqa: N806

        def flush_chunk() -> None:
            """
            Emit the current chunk to results, clearing state.
            Only emits if all state fields are valid.
            """
            nonlocal chunk_lines, line_numbers, match_line_num, current_path, prefix_regex

            if not chunk_lines or not line_numbers or current_path is None or match_line_num is None:
                # Incomplete/inactive chunk, reset and skip
                chunk_lines.clear()
                line_numbers.clear()
                match_line_num = None
                current_path = None
                prefix_regex = None
                return

            start_line, end_line = min(line_numbers), max(line_numbers)

            # Use precompiled prefix_regex for all lines in this chunk
            cleaned: List[str] = []
            for raw in chunk_lines:
                if prefix_regex is not None:
                    clean = prefix_regex.sub("", raw).rstrip()
                else:
                    clean = raw.rstrip()
                if len(clean) > MAX_LEN:
                    orig = len(clean)
                    half = MAX_LEN // 2 - 3
                    clean = f"{clean[:half]} … {clean[-half:]} (truncated, {orig} chars)"
                cleaned.append(clean)

            results.append(
                {
                    "chunk_info": ChunkInfo(
                        content="\n".join(cleaned),
                        source_details=ChunkSourceDetails(
                            file_path=current_path,
                            start_line=start_line,
                            end_line=end_line,
                        ),
                    ),
                    "matched_line": match_line_num,
                }
            )

            # Reset for next chunk
            chunk_lines.clear()
            line_numbers.clear()
            match_line_num = None
            current_path = None
            prefix_regex = None

        # ------------------------------------------------------------------
        # Stream and group JSON events into context/match chunks
        # ------------------------------------------------------------------
        for raw_line in json_lines:
            event = json.loads(raw_line)
            etype = event.get("type")
            if etype not in ("match", "context"):
                continue  # skip summary/begin/end events

            data = event["data"]
            path = data["path"]["text"]  # Always relative (cwd=repo_path)
            lno: int = data["line_number"]
            text = data["lines"]["text"].rstrip("\n")

            # New file, or explicit break? Emit previous chunk and start new
            if (current_path is not None and path != current_path) or (etype == "context" and data.get("break", False)):
                flush_chunk()

            # On path switch, recompile the prefix regex for this file
            if current_path != path:
                current_path = path
                if current_path is not None:
                    prefix_regex = re.compile(rf"^{re.escape(current_path)}:(\d+):")
                else:
                    prefix_regex = None

            # Append grep-style line for output formatting
            chunk_lines.append(f"{path}:{lno}:{text}")
            line_numbers.append(lno)

            if etype == "match":
                match_line_num = lno

        # Flush the final chunk (if any)
        flush_chunk()
        return results
