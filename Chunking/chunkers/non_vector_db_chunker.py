from concurrent.futures import ProcessPoolExecutor
from typing import List, Tuple

from models.chunk_info import ChunkInfo
from chunkers.base_chunker import BaseChunker
from utils.document import Document, chunks_to_docs
from utils.base_local_repo import BaseLocalRepo


class NonVectorDBChunker(BaseChunker):
    def __init__(self, local_repo: BaseLocalRepo, process_executor: ProcessPoolExecutor, use_new_chunking: bool = True):
        super().__init__(local_repo, process_executor)
        self.use_new_chunking = use_new_chunking

    async def create_chunks_and_docs(self) -> Tuple[List[ChunkInfo], List[Document]]:
        file_list = await self.local_repo.get_chunkable_files()
        all_chunks: List[ChunkInfo] = await self.file_chunk_creator.create_chunks_from_files(
            {file: None for file in file_list},
            self.local_repo.repo_path,
            self.use_new_chunking,
            process_executor=self.process_executor,
        )

        return all_chunks, chunks_to_docs(all_chunks)
