import asyncio
from asyncio.subprocess import PIPE
from pathlib import Path
from typing import Dict, List, Optional

from deputydev_core.services.repo.local_repo.base_local_repo_service import (
    BaseLocalRepo,
)


class NonVCSRepo(BaseLocalRepo):
    def __init__(
        self, repo_path: str, chunkable_files: Optional[List[str]] = None, ripgrep_path: Optional[str] = None
    ) -> None:
        super().__init__(repo_path, chunkable_files=chunkable_files, ripgrep_path=ripgrep_path)
        # cache ignore globs once
        exclude_dirs = self.chunk_config.exclude_dirs
        exclude_exts = self.chunk_config.exclude_exts
        # Build the ripgrep --glob patterns ONCE
        self.rg_glob_args: list[str] = []
        for d in exclude_dirs:
            # Exclude dir at any depth (works for 95% of cases)
            self.rg_glob_args.extend(["--glob", f"!{d}/**"])
            self.rg_glob_args.extend(["--glob", f"!*/{d}/**"])  # Extra for nested dirs
        for ext in exclude_exts:
            if ext.startswith("."):
                self.rg_glob_args.extend(["--glob", f"!*{ext}"])
            else:
                self.rg_glob_args.extend(["--glob", f"!*{ext}"])

    # ------------------------------------------------------------------ #
    # NEW ripgrep-based implementation
    # ------------------------------------------------------------------ #
    async def get_chunkable_files(self) -> List[str]:
        """
        List all files under the repo that are *not* in the ignore dirs,
        honouring .gitignore and skipping hidden files.
        Returns paths **relative to repo root**.
        """
        cmd = [
            self.ripgrep_path,
            "--files",  # list files only
            *self.rg_glob_args,  # extra ignore globs
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.repo_path,  # run inside the repo
            stdout=PIPE,
            stderr=PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            # rg returns 1 when no files match, >1 on error
            if proc.returncode == 1:
                return []
            raise RuntimeError(f"ripgrep failed (code {proc.returncode}): {stderr.decode().strip()}")

        # split lines, filter out empty strings, ensure posix separators
        rel_files = [Path(line).as_posix() for line in stdout.decode().splitlines() if line]
        chunkable_files = [f for f in rel_files if self._is_file_chunkable(f)]
        return chunkable_files

    async def get_chunkable_files_and_commit_hashes(self) -> Dict[str, str]:
        """Get all files in the repo and their hashes."""
        file_list = await self.get_chunkable_files()
        if self.chunkable_files:
            file_list = list(set(file_list) & set(self.chunkable_files))
        file_hashes: Dict[str, str] = {}
        for file in file_list:
            file_hashes[file] = self._get_file_hash(file)
        return file_hashes

    async def get_chunkable_files_and_commit_hashes_from_list(self, files: List[str]) -> Dict[str, str]:
        """
        Given a list of relative file paths, filter them to only include chunkable files,
        and return a dict mapping each chunkable file to its hash.
        """
        # Ensure posix-style paths
        rel_files = [Path(f).as_posix() for f in files if f]

        # Filter to only chunkable files
        chunkable_files = [f for f in rel_files if self._is_file_chunkable(f)]

        # If a specific subset of chunkable_files is pre-specified, intersect
        if self.chunkable_files:
            chunkable_files = list(set(chunkable_files) & set(self.chunkable_files))

        # Build file-hash mapping
        file_hashes: Dict[str, str] = {}
        for file in chunkable_files:
            file_hashes[file] = self._get_file_hash(file)

        return file_hashes
