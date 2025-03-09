from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from prompt_toolkit.shortcuts.progress_bar import (ProgressBar,
                                                   ProgressBarCounter)

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.chunker.handlers.vector_db_chunker import \
    VectorDBChunker
from deputydev_core.services.embedding.one_dev_embedding_manager import \
    OneDevEmbeddingManager
from deputydev_core.services.repo.local_repo.base_local_repo_service import \
    BaseLocalRepo
from deputydev_core.services.repository.dataclasses.main import \
    WeaviateSyncAndAsyncClients
from deputydev_core.utils.app_logger import AppLogger


class OneDevCLIChunker(VectorDBChunker):
    def __init__(
        self,
        local_repo: BaseLocalRepo,
        process_executor: ProcessPoolExecutor,
        weaviate_client: WeaviateSyncAndAsyncClients,
        embedding_manager: OneDevEmbeddingManager,
        chunkable_files_and_hashes: Dict[str, str],
        progress_bar: Optional[ProgressBar] = None,
        use_new_chunking: bool = True,
        use_async_refresh: bool = True,
        fetch_with_vector: bool = False,
    ):
        super().__init__(
            local_repo,
            process_executor,
            weaviate_client,
            embedding_manager,
            chunkable_files_and_hashes,
            use_new_chunking,
            use_async_refresh,
            fetch_with_vector,
        )
        self.embedding_manager = embedding_manager
        self.progress_bar = progress_bar
        self.file_progressbar_counter: Optional[ProgressBarCounter[int]] = None

    async def add_chunk_embeddings(self, chunks: List[ChunkInfo], len_checkpoints: Optional[int] = None) -> None:
        texts_to_embed = [
            chunk.get_chunk_content_with_meta_data(add_ellipsis=False, add_lines=False, add_class_function_info=True)
            for chunk in chunks
        ]
        embeddings, _input_tokens = await self.embedding_manager.embed_text_array(
            texts=texts_to_embed,
            progress_bar_counter=self.file_progressbar_counter,
            len_checkpoints=len_checkpoints,
        )
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

    async def get_file_wise_chunks_for_single_file_batch(
        self,
        files_to_chunk_batch: List[Tuple[str, str]],
    ) -> Dict[str, List[ChunkInfo]]:
        """
        Handles a batch of files to be chunked
        """
        file_wise_chunks = await self.file_chunk_creator.create_and_get_file_wise_chunks(
            dict(files_to_chunk_batch),
            self.local_repo.repo_path,
            self.use_new_chunking,
            process_executor=self.process_executor,
        )

        batched_chunks: List[ChunkInfo] = []
        for chunks in file_wise_chunks.values():
            batched_chunks.extend(chunks)
        if batched_chunks:
            await self.add_chunk_embeddings(batched_chunks, len_checkpoints=len(files_to_chunk_batch))
        else:
            if self.file_progressbar_counter:
                for _ in range(len(files_to_chunk_batch)):
                    self.file_progressbar_counter.item_completed()

        return file_wise_chunks

    async def create_and_store_chunks_for_file_batches(
        self,
        batched_files_to_store: List[List[Tuple[str, str]]],
        custom_timestamp: Optional[datetime] = None,
    ) -> Dict[str, List[ChunkInfo]]:
        total_files = sum(len(batch_files) for batch_files in batched_files_to_store)
        if self.progress_bar and total_files:
            self.file_progressbar_counter = self.progress_bar(
                range(total_files),
                label="Setting up DeputyDev's intelligence",
                remove_when_done=True,
            )
            AppLogger.log_debug(f"Processing {len(range(total_files))} batches")

        chunks_to_return = await super().create_and_store_chunks_for_file_batches(
            batched_files_to_store, custom_timestamp=custom_timestamp
        )
        if self.file_progressbar_counter:
            self.file_progressbar_counter.done = True
        return chunks_to_return
