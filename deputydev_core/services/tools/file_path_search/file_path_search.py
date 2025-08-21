from pathlib import Path
from typing import List, Optional

from fuzzywuzzy import fuzz

from deputydev_core.errors.tools.tool_errors import (
    EmptyToolResponseError,
    InvalidToolParamsError,
    UnhandledToolError,
)


class FilePathSearch:
    def __init__(self, repo_path: str) -> None:
        if not repo_path.strip():
            raise InvalidToolParamsError("`repo_path` must be a non-empty string.")
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.is_dir():
            raise InvalidToolParamsError(f"`repo_path` is not a directory: {repo_path}")

    def list_files(  # noqa: C901
        self,
        directory: str,
        search_terms: Optional[List[str]] = None,
        threshold: int = 70,
    ) -> List[str]:
        """
        List matching files under `directory` (relative to repo root).

        - If >100 matches, returns 101 items: first 100 + a final info string with total.
        - If `directory` doesn't exist inside the repo, raises InvalidToolParamsError (no fallback).
        - If nothing matches, raises EmptyToolResponseError.
        """
        try:
            # Normalize directory (treat "/", ".", "" as repo root), ensure relative semantics
            dir_arg = directory.strip()
            if dir_arg in ("/", ".", ""):
                dir_arg = ""
            dir_arg = dir_arg.lstrip("/\\")  # prevent absolute paths

            abs_dir_path = (self.repo_path / dir_arg).resolve()

            # Must be inside repo
            try:
                abs_dir_path.relative_to(self.repo_path)
            except ValueError:
                raise InvalidToolParamsError("`directory` must be inside the repository.")
            if not abs_dir_path.is_dir():
                raise InvalidToolParamsError(f"`directory` does not exist: {directory or '/'}")

            matches: List[str] = []
            total_matches = 0

            # Walk with pathlib
            for p in abs_dir_path.rglob("*"):
                if not p.is_file():
                    continue

                rel_path = p.relative_to(self.repo_path).as_posix()
                parts = rel_path.split("/")

                is_match = True
                if search_terms:
                    is_match = any(
                        fuzz.ratio(term.lower(), part.lower()) >= threshold for term in search_terms for part in parts
                    )

                if is_match:
                    total_matches += 1
                    if len(matches) < 100:
                        matches.append(rel_path)

            if total_matches == 0:
                raise EmptyToolResponseError(f"No matching files found in '{directory or '/'}'.")

            if total_matches > 100:
                matches.append(
                    f"[RESULTS TRUNCATED] {total_matches} files matched in '{directory or '/'}'. "
                    f"Showing first 100. Refine search_terms or directory."
                )

            return matches

        except (InvalidToolParamsError, EmptyToolResponseError):
            raise
        except Exception as e:
            raise UnhandledToolError(f"File path search failed: {e}") from e
