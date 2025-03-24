import asyncio
import os
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Mapping, Optional

from deputydev_core.utils.config_manager import ConfigManager

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.source_chunker import chunk_source
from deputydev_core.services.repo.local_repo.base_local_repo_service import (
    BaseLocalRepo,
)
from deputydev_core.utils.config_setter import set_config
from deputydev_core.utils.file_utils import read_file


# This is a utility class and functions are static to handle pickling during process forking seamlessly
class FileChunkCreator:
    @staticmethod
    def create_chunks(
        file_path: str,
        root_dir: str,
        file_hash: Optional[str] = None,
        use_new_chunking: bool = False,
        config: Dict = None
    ) -> list[ChunkInfo]:
        """
        Converts the content of a file into chunks of code.

        Args:
            source (str): The path to the file to be processed.
            use_new_chunking(bool): to enabled new chunking strategy

        Returns:
            list[str]: A list of code chunks extracted from the file.
        """
        if config:
            set_config(config)
        file_contents = read_file(os.path.join(root_dir, file_path))
        chunks = chunk_source(
            file_contents,
            path=file_path,
            file_hash=file_hash,
            nl_desc=False,
            use_new_chunking=use_new_chunking,
        )
        return chunks

    @staticmethod
    async def create_and_get_file_wise_chunks(
        file_paths_and_hashes: Mapping[str, Optional[str]],
        root_dir: str,
        use_new_chunking: bool = False,
        process_executor: Optional[ProcessPoolExecutor] = None,
        set_config_in_new_process: bool = False
    ) -> Dict[str, List[ChunkInfo]]:
        """
        Converts the content of a list of files into chunks of code.

        Args:
            file_path (List[str]): A list of file paths to be processed.

        Returns:
            List[ChunkInfo]: A list of code chunks extracted from the files.
        """

        file_wise_chunks: Dict[str, List[ChunkInfo]] = {}

        loop = asyncio.get_event_loop()
        for file, file_hash in file_paths_and_hashes.items():
            chunks_from_file: List[ChunkInfo] = []
            if process_executor is None:
                chunks_from_file = FileChunkCreator.create_chunks(file, root_dir, file_hash, use_new_chunking)
            else:
                chunks_from_file = await loop.run_in_executor(
                    process_executor,
                    FileChunkCreator.create_chunks,
                    file,
                    root_dir,
                    file_hash,
                    use_new_chunking,
                    ConfigManager.configs if set_config_in_new_process else None
                )
            file_wise_chunks[file] = chunks_from_file

        return file_wise_chunks


class BaseChunker(ABC):
    def __init__(self, local_repo: BaseLocalRepo, process_executor: ProcessPoolExecutor) -> None:
        self.local_repo = local_repo
        self.process_executor = process_executor
        self.file_chunk_creator = FileChunkCreator

    @abstractmethod
    async def create_chunks_and_docs(self) -> List[ChunkInfo]:
        raise NotImplementedError("create_chunks method must be implemented in the child class")
