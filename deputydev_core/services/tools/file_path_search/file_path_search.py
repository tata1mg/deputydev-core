import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Optional, Set

from fuzzywuzzy import fuzz

from deputydev_core.errors.tools.tool_errors import (
    EmptyToolResponseError,
    InvalidToolParamsError,
    UnhandledToolError,
)

_DEFAULT_IGNORED_DIRS: Set[str] = {
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".cache",
    ".git",
    ".hg",
    ".svn",
    "dist",
    "build",
    ".tox",
}


class FilePathSearch:
    def __init__(
        self,
        repo_path: str,
        *,
        ignore_dirs: Optional[Iterable[str]] = None,
        ignore_globs: Optional[Iterable[str]] = None,
        ignore_hidden: bool = True,
    ) -> None:
        """
        - ignore_dirs: directory basenames to prune anywhere in the tree (case-sensitive)
        - ignore_globs: path patterns (POSIX-style) to exclude, matched against repo-relative paths
        - ignore_hidden: prune any directory whose basename starts with '.'
        """
        if not repo_path.strip():
            raise InvalidToolParamsError("`repo_path` must be a non-empty string.")
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.is_dir():
            raise InvalidToolParamsError(f"`repo_path` is not a directory: {repo_path}")

        self.ignore_dirs: Set[str] = set(ignore_dirs or []) | set(_DEFAULT_IGNORED_DIRS)
        self.ignore_globs: List[str] = list(ignore_globs or [])
        self.ignore_hidden = ignore_hidden

    def _should_prune_dir(self, rel_dir_parts: Iterable[str]) -> bool:
        for part in rel_dir_parts:
            if self.ignore_hidden and part.startswith("."):
                return True
            if part in self.ignore_dirs:
                return True
        return False

    def _is_ignored_by_glob(self, rel_path_posix: str) -> bool:
        # apply to files/dirs using repo-relative posix path
        return any(fnmatch(rel_path_posix, pat) for pat in self.ignore_globs)

    def list_files(  # noqa: C901
        self,
        directory: str,
        search_terms: Optional[List[str]] = None,
        threshold: int = 70,
    ) -> List[str]:
        """
        List matching files under `directory` (relative to repo root), pruning ignored dirs.

        - If >100 matches, returns 101 items: first 100 + a final info string with total.
        - If `directory` doesn't exist inside the repo, raises InvalidToolParamsError (no fallback).
        - If nothing matches, raises EmptyToolResponseError.
        """
        try:
            # Normalize directory (treat "/", ".", "" as repo root), ensure relative semantics
            dir_arg = (directory or "").strip()
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

            # Walk and prune in-place
            for root, dirs, files in os.walk(abs_dir_path):
                root_path = Path(root).resolve()
                rel_root = root_path.relative_to(self.repo_path)
                rel_root_parts = rel_root.parts

                # prune by dir names / hidden
                if self._should_prune_dir(rel_root_parts):
                    # Skip processing this subtree by clearing dirs (no descend)
                    dirs[:] = []
                    continue

                # prune children dirs before descending
                pruned_dirs = []
                for d in dirs:
                    rel_child = (rel_root / d).as_posix()
                    if (
                        d in self.ignore_dirs
                        or (self.ignore_hidden and d.startswith("."))
                        or self._is_ignored_by_glob(rel_child)
                    ):
                        continue
                    pruned_dirs.append(d)
                dirs[:] = pruned_dirs  # in-place modification prunes traversal

                # process files
                for fname in files:
                    rel_path = (rel_root / fname).as_posix()
                    # glob-based ignore for files too
                    if self._is_ignored_by_glob(rel_path):
                        continue

                    parts = rel_path.split("/")

                    is_match = True
                    if search_terms:
                        is_match = any(
                            fuzz.ratio(term.lower(), part.lower()) >= threshold
                            for term in search_terms
                            for part in parts
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
