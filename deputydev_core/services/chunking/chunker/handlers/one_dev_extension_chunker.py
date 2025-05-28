from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.chunker.handlers.vector_db_chunker import (
    VectorDBChunker,
)
from deputydev_core.services.chunking.vector_store.chunk_vectore_store_manager import (
    ChunkVectorStoreManager,
)
from deputydev_core.services.embedding.extension_embedding_manager import (
    ExtensionEmbeddingManager,
)
from deputydev_core.services.embedding.pr_review_embedding_manager import (
    PRReviewEmbeddingManager,
)
from deputydev_core.services.repo.local_repo.base_local_repo_service import (
    BaseLocalRepo,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)
from deputydev_core.utils.custom_progress_bar import CustomProgressBar


class OneDevExtensionChunker(VectorDBChunker):
    def __init__(
        self,
        local_repo: BaseLocalRepo,
        process_executor: ProcessPoolExecutor,
        weaviate_client: WeaviateSyncAndAsyncClients,
        embedding_manager: Union[ExtensionEmbeddingManager, PRReviewEmbeddingManager],
        chunkable_files_and_hashes: Dict[str, str],
        progress_bar: Optional[CustomProgressBar] = None,
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
            set_config_in_new_process=True,
        )

        # WARNING: Do not change this to pass by value, it will increase memory usage
        batched_chunks: List[ChunkInfo] = []
        for chunks in file_wise_chunks.values():
            batched_chunks.extend(chunks)

        if batched_chunks:
            await self.add_chunk_embeddings(batched_chunks)
        return file_wise_chunks

    async def create_and_store_chunks_for_file_batches(
        self,
        batched_files_to_store: List[List[Tuple[str, str]]],
        custom_timestamp: Optional[datetime] = None,
    ) -> Dict[str, List[ChunkInfo]]:
        """
        Creates and stores chunks for a batch of files.
        Args:
            batched_files_to_store (List[List[Tuple[str, str]]]): A list of files to be chunked.
            custom_timestamp (Optional[datetime], optional): A custom timestamp to be used for chunking. Defaults to None.
        Returns:
            Dict[str, List[ChunkInfo]]: A dictionary of file wise chunks.
        """

        all_file_wise_chunks: Dict[str, List[ChunkInfo]] = {}
        if self.progress_bar:
            self.progress_bar.initialise(total_files_to_process=sum([len(files) for files in batched_files_to_store]))
        for batch_files in batched_files_to_store:
            if self.progress_bar:
                self.progress_bar.set_current_batch_percentage(len(batch_files))
            # get the chunks for the batch
            file_wise_chunks_for_batch = await self.get_file_wise_chunks_for_single_file_batch(
                files_to_chunk_batch=batch_files,
            )

            # store the chunks in the vector store
            await ChunkVectorStoreManager(
                local_repo=self.local_repo, weaviate_client=self.weaviate_client
            ).add_differential_chunks_to_store(
                file_wise_chunks_for_batch,
                custom_create_timestamp=custom_timestamp,
                custom_update_timestamp=custom_timestamp,
            )

            # remove the embeddings if not required
            if not self.fetch_with_vector:
                # remove the embeddings from the chunks
                for chunks in file_wise_chunks_for_batch.values():
                    for chunk in chunks:
                        chunk.embedding = None

            # merge the chunks
            all_file_wise_chunks.update(file_wise_chunks_for_batch)
        if self.progress_bar:
            self.progress_bar.mark_finish()
        return all_file_wise_chunks

    async def add_chunk_embeddings(self, chunks: List[ChunkInfo]) -> None:
        """
        Adds embeddings to the chunks.

        Args:
            chunks (List[ChunkInfo]): A list of chunks to which embeddings should be added.

        Returns:
            List[ChunkInfo]: A list of chunks with embeddings added.
        """
        texts_to_embed = [
            chunk.get_chunk_content_with_meta_data(add_ellipsis=False, add_lines=False, add_class_function_info=True)
            for chunk in chunks
        ]
        embeddings, _input_tokens = await self.embedding_manager.embed_text_array(
            texts=texts_to_embed, progress_bar_counter=self.progress_bar
        )
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
