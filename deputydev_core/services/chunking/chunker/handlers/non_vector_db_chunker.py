"""
This module contains the NonVectorDBChunker class, which is used to chunk files on the fly for a local repository.
"""

from concurrent.futures import ProcessPoolExecutor
from typing import List

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.chunker.base_chunker import BaseChunker
from deputydev_core.services.repo.local_repo.base_local_repo_service import \
    BaseLocalRepo


class NonVectorDBChunker(BaseChunker):
    def __init__(
        self,
        local_repo: BaseLocalRepo,
        process_executor: ProcessPoolExecutor,
        use_new_chunking: bool = True,
    ):
        super().__init__(local_repo, process_executor)
        self.use_new_chunking = use_new_chunking

    async def create_chunks_and_docs(self) -> List[ChunkInfo]:
        file_list = await self.local_repo.get_chunkable_files()
        file_wise_chunks = await self.file_chunk_creator.create_and_get_file_wise_chunks(
            {file: None for file in file_list},
            self.local_repo.repo_path,
            self.use_new_chunking,
            process_executor=self.process_executor,
        )
        all_chunks: List[ChunkInfo] = []
        for chunks in file_wise_chunks.values():
            all_chunks.extend(chunks)

        return all_chunks
