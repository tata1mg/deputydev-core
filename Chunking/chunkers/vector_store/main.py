import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from models.chunk_dto import ChunkDTO, ChunkDTOWithVector
from models.chunk_file_dto import ChunkFileDTO
from models.chunk_info import ChunkInfo
from utils.base_local_repo import BaseLocalRepo
from repository.chunk_service import ChunkService
from repository.chunk_files_service import ChunkFilesService
from repository.chunk_usages_service import ChunkUsagesService
from repository.dataclasses.main import WeaviateSyncAndAsyncClients


class ChunkVectorScoreManager:
    def __init__(self, local_repo: BaseLocalRepo, weaviate_client: WeaviateSyncAndAsyncClients):
        self.local_repo = local_repo
        self.weaviate_client = weaviate_client

    async def get_stored_chunk_files_with_chunk_content(
            self, file_path_commit_hash_map: Dict[str, str]
    ) -> List[Tuple[ChunkFileDTO, ChunkDTO]]:
        """
        Get files to chunk and store based on the file path and commit hash map and files already present in the vector store.
        :param file_path_commit_hash_map: Dict[str, str]
        :return: Dict[str, str]
        """
        chunk_files_in_db = await ChunkFilesService(
            weaviate_client=self.weaviate_client
        ).get_chunk_files_by_commit_hashes(file_to_commit_hashes=file_path_commit_hash_map)

        if not chunk_files_in_db:
            return []

        stored_chunks = await ChunkService(weaviate_client=self.weaviate_client).get_chunks_by_chunk_hashes(
            chunk_hashes=[chunk_file.chunk_hash for chunk_file in chunk_files_in_db]
        )

        stored_chunks_chunk_dict = {chunk.chunk_hash: chunk for chunk in stored_chunks}
        all_chunk_files_and_chunks = [
            (chunk_file, stored_chunks_chunk_dict[chunk_file.chunk_hash])
            for chunk_file in chunk_files_in_db
            if chunk_file.chunk_hash in stored_chunks_chunk_dict
        ]
        return all_chunk_files_and_chunks

    async def add_differential_chunks_to_store(self, chunks: List[ChunkInfo], usage_hash: str) -> None:
        """
        Add differential chunks to the vector store.
        :param chunks: List[FileWithChunks]
        :return: List[ChunkDTO]
        """
        all_chunks_to_store: List[ChunkDTOWithVector] = []
        all_chunk_files_to_store: List[ChunkFileDTO] = []

        for chunk in chunks:
            if chunk.embedding is None or not chunk.source_details.file_hash:
                raise ValueError(f"Chunk {chunk.content_hash} does not have an embedding")

            now_time = datetime.now().replace(tzinfo=timezone.utc)
            all_chunks_to_store.append(
                ChunkDTOWithVector(
                    dto=ChunkDTO(
                        chunk_hash=chunk.content_hash,
                        text=chunk.content,
                        created_at=now_time,
                        updated_at=now_time,
                    ),
                    vector=chunk.embedding,
                ),
            )
            all_chunk_files_to_store.append(
                ChunkFileDTO(
                    file_path=chunk.source_details.file_path,
                    chunk_hash=chunk.content_hash,
                    file_hash=chunk.source_details.file_hash,
                    start_line=chunk.source_details.start_line,
                    end_line=chunk.source_details.end_line,
                    created_at=now_time,
                    updated_at=now_time,
                )
            )

        await asyncio.gather(
            ChunkService(weaviate_client=self.weaviate_client).bulk_insert(all_chunks_to_store),
            ChunkFilesService(weaviate_client=self.weaviate_client).bulk_insert(all_chunk_files_to_store),
        )

        ChunkUsagesService(weaviate_client=self.weaviate_client).add_chunk_usage(
            chunk_hashes=[chunk.dto.chunk_hash for chunk in all_chunks_to_store],
            usage_hash=usage_hash,
            force_create_references=True,
        )
