import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Union

from xxhash import xxh64

from deputydev_core.services.chunking.config.chunk_config import ChunkConfig
from deputydev_core.services.repo.local_repo.dataclasses.main import DiffTypes
from deputydev_core.services.repo.local_repo.diff_applicators.line_numbered_diff.applicator import (
    LineNumberedDiffApplicator,
)
from deputydev_core.services.repo.local_repo.diff_applicators.unified_diff.applicator import UnifiedDiffApplicator
from deputydev_core.utils.app_logger import AppLogger


class BaseLocalRepo(ABC):
    def __init__(
        self,
        repo_path: str,
        chunk_config: Optional[ChunkConfig] = None,
        chunkable_files: List = None,
    ):
        self.repo_path = repo_path
        self.chunk_config = chunk_config or ChunkConfig()
        self.chunkable_files = chunkable_files if chunkable_files else []

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

    def apply_diff(
        self, diff: Dict[str, Union[List[Tuple[int, int, str]], str]], diff_type: DiffTypes = DiffTypes.LINE_NUMBERED
    ) -> None:
        if diff_type == DiffTypes.LINE_NUMBERED:
            line_numed_diff_applicator = LineNumberedDiffApplicator(self.repo_path)
            line_numed_diff_applicator.apply_diff(diff)
        else:
            udiff_applicator = UnifiedDiffApplicator(self.repo_path)
            udiff_applicator.apply_diff(diff)

    def get_modified_file_content(
        self, diff: Dict[str, Union[List[Tuple[int, int, str]], str]], diff_type: DiffTypes = DiffTypes.LINE_NUMBERED
    ) -> Dict[str, str]:
        if diff_type == DiffTypes.LINE_NUMBERED:
            line_numed_diff_applicator = LineNumberedDiffApplicator(self.repo_path)
            modified_content_lines = line_numed_diff_applicator.get_final_content(diff)
            return {
                file_path: "".join(modified_content_lines)
                for file_path, modified_content_lines in modified_content_lines.items()
            }
        else:
            udiff_applicator = UnifiedDiffApplicator(self.repo_path)
            return udiff_applicator.get_final_content(diff)
