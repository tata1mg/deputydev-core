import os
from typing import Dict, List

from deputydev_core.services.repo.local_repo.base_local_repo_service import (
    BaseLocalRepo,
)


class NonVCSRepo(BaseLocalRepo):
    def __init__(self, repo_path: str, chunkable_files: List[str] = None):
        super().__init__(repo_path, chunkable_files=chunkable_files)

    async def get_chunkable_files(self) -> List[str]:
        ignore_dirs = {"node_modules", ".venv", "build", "venv", "patch"}
        all_files: List[str] = []
        for dirpath, dirnames, filenames in os.walk(self.repo_path):
            # Filter ignored directories
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
            for file in filenames:
                # append relative path to the file
                all_files.append(os.path.relpath(os.path.join(dirpath, file), self.repo_path))
        return all_files

    async def get_chunkable_files_and_commit_hashes(self) -> Dict[str, str]:
        """Get all files in the repo and their hashes."""
        file_list = await self.get_chunkable_files()
        if self.chunkable_files:
            file_list = list(set(file_list) & set(self.chunkable_files))
        file_hashes: Dict[str, str] = {}
        for file in file_list:
            file_hashes[file] = self._get_file_hash(file)
        return file_hashes
