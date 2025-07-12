from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from xxhash import xxh64

from deputydev_core.services.chunking.config.chunk_config import ChunkConfig
from deputydev_core.utils.app_logger import AppLogger


class BaseLocalRepo(ABC):
    def __init__(
        self,
        repo_path: str,
        chunk_config: Optional[ChunkConfig] = None,
        chunkable_files: Optional[List[str]] = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.chunk_config = chunk_config or ChunkConfig()
        self.chunkable_files = chunkable_files or []

    def _get_file_hash(self, file_path: str) -> str:
        file_full_path = self.repo_path / file_path
        with file_full_path.open("rb") as file:
            file_content = file.read()
            return xxh64(file_content).hexdigest()

    def _is_file_chunkable(self, file_path: str) -> bool:
        try:
            abs_file_path = self.repo_path / file_path
            file_ext = abs_file_path.suffix
            if file_ext.lower() in self.chunk_config.exclude_exts:
                return False
            if not abs_file_path.is_file():
                return False
            if abs_file_path.stat().st_size > self.chunk_config.max_chunkable_file_size_bytes:
                AppLogger.log_debug(f"File size is greater than the max_chunkable_file_size_bytes: {abs_file_path}")
                return False
            # Exclude if any parent directory's name matches an exclude_dir
            if any(parent.name in self.chunk_config.exclude_dirs for parent in abs_file_path.parents):
                return False
            return True
        except Exception as ex:  # noqa: BLE001
            AppLogger.log_debug(f"Error while checking if file is chunkable: {ex} for file: {file_path}")
            return False

    @abstractmethod
    async def get_chunkable_files_and_commit_hashes(self) -> Dict[str, str]:
        raise NotImplementedError("get_file_to_commit_hash_map method must be implemented in the child class")

    @abstractmethod
    async def get_chunkable_files(self) -> List[str]:
        raise NotImplementedError("get_chunkable_files method must be implemented in the child class")
