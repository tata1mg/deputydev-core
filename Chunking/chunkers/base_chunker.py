import asyncio
import os
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor
from typing import List, Mapping, Optional, Tuple

from chunkers.chunk import chunk_source
from models.chunk_info import ChunkInfo
from utils.document import Document
from utils.base_local_repo import BaseLocalRepo
from utils.file_utils import read_file


# This is a utility class and functions are static to handle pickling during process forking seamlessly
class FileChunkCreator:
    @staticmethod
    def create_chunks(
            file_path: str, root_dir: str, file_hash: Optional[str] = None, use_new_chunking: bool = False
    ) -> list[ChunkInfo]:
        """
        Converts the content of a file into chunks of code.

        Args:
            source (str): The path to the file to be processed.
            use_new_chunking(bool): to enabled new chunking strategy

        Returns:
            list[str]: A list of code chunks extracted from the file.
        """
        file_contents = read_file(os.path.join(root_dir, file_path))
        chunks = chunk_source(
            file_contents, path=file_path, file_hash=file_hash, nl_desc=False, use_new_chunking=use_new_chunking
        )
        return chunks

    @staticmethod
    async def create_chunks_from_files(
            file_paths_and_hashes: Mapping[str, Optional[str]],
            root_dir: str,
            use_new_chunking: bool = False,
            process_executor: Optional[ProcessPoolExecutor] = None,
    ) -> List[ChunkInfo]:
        """
        Converts the content of a list of files into chunks of code.

        Args:
            file_path (List[str]): A list of file paths to be processed.

        Returns:
            List[ChunkInfo]: A list of code chunks extracted from the files.
        """
        chunks: List[ChunkInfo] = []

        loop = asyncio.get_event_loop()
        for file, file_hash in file_paths_and_hashes.items():
            chunks_from_file: List[ChunkInfo] = []
            if process_executor is None:
                chunks_from_file = FileChunkCreator.create_chunks(file, root_dir, file_hash, use_new_chunking)
            else:
                chunks_from_file = await loop.run_in_executor(
                    process_executor, FileChunkCreator.create_chunks, file, root_dir, file_hash, use_new_chunking
                )
            chunks.extend(chunks_from_file)
        return chunks


class BaseChunker(ABC):
    def __init__(self, local_repo: BaseLocalRepo, process_executor: ProcessPoolExecutor) -> None:
        self.local_repo = local_repo
        self.process_executor = process_executor
        self.file_chunk_creator = FileChunkCreator

    @abstractmethod
    async def create_chunks_and_docs(self) -> Tuple[List[ChunkInfo], List[Document]]:
        raise NotImplementedError("create_chunks method must be implemented in the child class")
