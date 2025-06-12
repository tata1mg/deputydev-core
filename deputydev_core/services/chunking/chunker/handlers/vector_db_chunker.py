"""
This module contains the VectorDBChunker class, which is used to chunk files and store them in the vector store.
The VectorDBChunker class is a subclass of the BaseChunker class and implements the create_chunks_and_docs method.
This is used to chunk a given list of files and store them in the vector store.
"""

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.chunker.base_chunker import BaseChunker
from deputydev_core.services.chunking.vector_store.chunk_vectore_store_manager import (
    ChunkVectorStoreManager,
)
from deputydev_core.services.chunking.vector_store.dataclasses.refresh_config import (
    RefreshConfig,
)
from deputydev_core.services.embedding.base_embedding_manager import (
    BaseEmbeddingManager,
)
from deputydev_core.services.repo.local_repo.base_local_repo_service import (
    BaseLocalRepo,
)
from deputydev_core.services.repository.dataclasses.main import (
    WeaviateSyncAndAsyncClients,
)


class VectorDBChunker(BaseChunker):
    def __init__(
        self,
        local_repo: BaseLocalRepo,
        process_executor: ProcessPoolExecutor,
        weaviate_client: WeaviateSyncAndAsyncClients,
        embedding_manager: BaseEmbeddingManager,
        chunkable_files_and_hashes: Optional[Dict[str, str]] = None,
        use_new_chunking: bool = True,
        use_async_refresh: bool = False,
        fetch_with_vector: bool = False,
    ):
        """
        Initializes the VectorDBChunker class.
        Args:
            local_repo (BaseLocalRepo): A object to interact with the local repository.
            process_executor (ProcessPoolExecutor): A process executor, used for parallel processing of chunks.
            weaviate_client (WeaviateSyncAndAsyncClients): The Weaviate client.
            embedding_manager (BaseEmbeddingManager): The embedding manager.
            chunkable_files_and_hashes (Optional[Dict[str, str]], optional): The chunkable files and hashes. Defaults to None.
            use_new_chunking (bool, optional): Whether to use the new chunking strategy. Defaults to True.
            use_async_refresh (bool, optional): Whether to wait for chunk timestamp refresh before moving on to next batch of files. Defaults to False.
            fetch_with_vector (bool, optional): Whether to return ChunkInfo with embeddings. Defaults to False.

        Returns:
            None
        """
        super().__init__(local_repo, process_executor)
        self.use_new_chunking = use_new_chunking
        self.weaviate_client = weaviate_client
        self.embedding_manager = embedding_manager
        self.chunkable_files_and_hashes = chunkable_files_and_hashes
        self.use_async_refresh = use_async_refresh
        self.fetch_with_vector = fetch_with_vector

    def batchify_files_for_insertion(
        self, files_to_chunk: Dict[str, str], max_batch_size_chunking: int = 200
    ) -> List[List[Tuple[str, str]]]:
        files_to_chunk_items = list(files_to_chunk.items())
        batched_files_to_store: List[List[Tuple[str, str]]] = []
        for i in range(0, len(files_to_chunk), max_batch_size_chunking):
            # create batch chunks
            batch_files = files_to_chunk_items[i : i + max_batch_size_chunking]
            batched_files_to_store.append(batch_files)

        return batched_files_to_store

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
        embeddings, _input_tokens = await self.embedding_manager.embed_text_array(texts=texts_to_embed)
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

        for batch_files in batched_files_to_store:
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
        return all_file_wise_chunks

    async def create_chunks_and_docs(self, enable_refresh=False) -> List[ChunkInfo]:
        """
        Converts the content of a list of files into chunks of code.
        Returns:
            List[ChunkInfo]: A list of code chunks extracted from the files.

        """
        # determine chunking timestamp
        chunking_timestamp = datetime.now().replace(tzinfo=timezone.utc)

        # get all the files and their commit hashes
        file_path_commit_hash_map = self.chunkable_files_and_hashes
        if not file_path_commit_hash_map:
            file_path_commit_hash_map = await self.local_repo.get_chunkable_files_and_commit_hashes()

        # get all the chunk_files and chunks stored in the vector store
        existing_file_wise_chunks = await ChunkVectorStoreManager(
            weaviate_client=self.weaviate_client, local_repo=self.local_repo
        ).get_valid_file_wise_stored_chunks(
            file_path_commit_hash_map,
            self.fetch_with_vector,
            chunk_refresh_config=RefreshConfig(
                async_refresh=self.use_async_refresh,
                refresh_timestamp=chunking_timestamp,
            ),
            enable_refresh=enable_refresh,
        )
        if self.file_indexing_progress_monitor and existing_file_wise_chunks:
            self.file_indexing_progress_monitor.update_status({key: "COMPLETED" for key in existing_file_wise_chunks})

        # get the files that need to be chunked
        files_to_chunk = {
            file: file_hash
            for file, file_hash in file_path_commit_hash_map.items()
            if file not in existing_file_wise_chunks.keys()
        }
        count = 0
        # Handle missing embeddings
        for file, chunks in existing_file_wise_chunks.items():
            if file in file_path_commit_hash_map:
                for chunk in chunks:
                    if not chunk.embedding:
                        count += 1
                        files_to_chunk[file] = file_path_commit_hash_map[file]
        print(f"Missing chunks which do not have embedding: {count}")
        # batchify the files for insertion
        batchified_files_for_insertion = self.batchify_files_for_insertion(
            files_to_chunk=files_to_chunk,
        )

        # create and store chunks for each batch
        missing_file_wise_chunks: Dict[str, List[ChunkInfo]] = await self.create_and_store_chunks_for_file_batches(
            batchified_files_for_insertion, custom_timestamp=chunking_timestamp
        )

        # merge the missing and existing chunks
        all_file_wise_chunks = {**missing_file_wise_chunks, **existing_file_wise_chunks}
        final_chunks: List[ChunkInfo] = []
        for chunks in all_file_wise_chunks.values():
            final_chunks.extend(chunks)

        return final_chunks
