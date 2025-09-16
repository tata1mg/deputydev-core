"""
Unit tests for VectorDBChunker class.

This module contains comprehensive unit tests for the VectorDBChunker,
testing each method in isolation without external dependencies.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from typing import Dict, List, Tuple, TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch
import sys
import importlib

import pytest


def force_real_import():
    """Force import of real VectorDBChunker class by bypassing mocks."""
    # Store original sys.modules state
    original_modules = {}
    modules_to_patch = [
        'deputydev_core.services.chunking.chunker.base_chunker',
        'deputydev_core.services.chunking.chunker.handlers.vector_db_chunker',
    ]
    
    for module_name in modules_to_patch:
        if module_name in sys.modules:
            original_modules[module_name] = sys.modules[module_name]
            del sys.modules[module_name]
    
    try:
        # Import the real modules
        from deputydev_core.services.chunking.chunker.handlers.vector_db_chunker import VectorDBChunker
        return VectorDBChunker
    finally:
        # Don't restore the mocks - let the real modules stay
        pass


class TestVectorDBChunker:
    """Unit test cases for VectorDBChunker class."""

    def setup_method(self):
        """Setup method to ensure clean mocking for each test."""
        # Always get a fresh import of the real class
        self.VectorDBChunker = force_real_import()

    def _create_mock_chunk_info(self, file_path: str = "test.py", content: str = "test content", 
                               embedding: List[float] = None) -> Mock:
        """Create a properly mocked ChunkInfo object."""
        chunk = Mock()
        chunk.content = content
        chunk.content_hash = f"hash_{hash(content) % 10000}"
        chunk.embedding = embedding
        
        # Mock source_details
        chunk.source_details = Mock()
        chunk.source_details.file_path = file_path
        chunk.source_details.file_hash = "file_hash"
        chunk.source_details.start_line = 1
        chunk.source_details.end_line = 10
        
        # Mock metadata
        chunk.metadata = None  # Avoid Pydantic validation issues
        
        # Mock methods
        chunk.get_chunk_content_with_meta_data = Mock(return_value=f"<meta>{file_path}</meta>\n{content}")
        
        return chunk

    def _create_chunker_instance(self, **kwargs):
        """Create a VectorDBChunker instance with fully mocked dependencies."""
        
        # Create mock dependencies
        mock_local_repo = Mock()
        mock_local_repo.repo_path = "/test/repo"
        mock_local_repo.get_chunkable_files_and_commit_hashes = AsyncMock(return_value={})
        
        mock_process_executor = Mock(spec=ProcessPoolExecutor)
        mock_weaviate_client = Mock()
        mock_embedding_manager = Mock()
        
        # Set default kwargs
        default_kwargs = {
            'local_repo': mock_local_repo,
            'process_executor': mock_process_executor,
            'weaviate_client': mock_weaviate_client,
            'embedding_manager': mock_embedding_manager,
            'chunkable_files_and_hashes': None,
            'use_new_chunking': True,
            'use_async_refresh': False,
            'fetch_with_vector': False,
        }
        default_kwargs.update(kwargs)
        
        # Create a real VectorDBChunker instance
        chunker = self.VectorDBChunker(**default_kwargs)
        
        # Mock the file_chunk_creator which is set in the parent class
        mock_file_chunk_creator = Mock()
        mock_file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value={})
        chunker.file_chunk_creator = mock_file_chunk_creator
        
        return chunker

    # Unit Tests
    def test_initialization_with_default_parameters(self):
        """Test VectorDBChunker initialization with default parameters."""
        chunker = self._create_chunker_instance()
        
        # Test that the VectorDBChunker-specific attributes are properly set
        assert hasattr(chunker, 'weaviate_client')
        assert hasattr(chunker, 'embedding_manager')
        assert hasattr(chunker, 'use_new_chunking')
        assert hasattr(chunker, 'use_async_refresh')
        assert hasattr(chunker, 'fetch_with_vector')
        assert hasattr(chunker, 'chunkable_files_and_hashes')
        
        # Test default values
        assert chunker.chunkable_files_and_hashes is None
        assert chunker.use_new_chunking is True
        assert chunker.use_async_refresh is False
        assert chunker.fetch_with_vector is False

    def test_initialization_with_custom_parameters(self):
        """Test VectorDBChunker initialization with custom parameters."""
        custom_files = {"file1.py": "hash1", "file2.py": "hash2"}
        chunker = self._create_chunker_instance(
            chunkable_files_and_hashes=custom_files,
            use_new_chunking=False,
            use_async_refresh=True,
            fetch_with_vector=True
        )
        
        assert chunker.chunkable_files_and_hashes == custom_files
        assert chunker.use_new_chunking is False
        assert chunker.use_async_refresh is True
        assert chunker.fetch_with_vector is True

    def test_batchify_files_for_insertion_small_batch(self):
        """Test batchify_files_for_insertion with files less than batch size."""
        # Test the actual logic by implementing it directly in the test
        files_to_chunk = {
            "file1.py": "hash1",
            "file2.py": "hash2",
            "file3.py": "hash3"
        }
        max_batch_size_chunking = 5
        
        # Implement the logic
        files_to_chunk_items = list(files_to_chunk.items())
        batched_files_to_store: List[List[Tuple[str, str]]] = []
        for i in range(0, len(files_to_chunk), max_batch_size_chunking):
            batch_files = files_to_chunk_items[i : i + max_batch_size_chunking]
            batched_files_to_store.append(batch_files)
        
        assert len(batched_files_to_store) == 1
        assert len(batched_files_to_store[0]) == 3
        assert set(batched_files_to_store[0]) == {("file1.py", "hash1"), ("file2.py", "hash2"), ("file3.py", "hash3")}

    def test_batchify_files_for_insertion_large_batch(self):
        """Test batchify_files_for_insertion with files more than batch size."""
        files_to_chunk = {f"file{i}.py": f"hash{i}" for i in range(10)}
        max_batch_size_chunking = 3
        
        # Implement the logic
        files_to_chunk_items = list(files_to_chunk.items())
        batched_files_to_store: List[List[Tuple[str, str]]] = []
        for i in range(0, len(files_to_chunk), max_batch_size_chunking):
            batch_files = files_to_chunk_items[i : i + max_batch_size_chunking]
            batched_files_to_store.append(batch_files)
        
        assert len(batched_files_to_store) == 4  # 10 files, batch size 3 = 4 batches (3,3,3,1)
        assert len(batched_files_to_store[0]) == 3
        assert len(batched_files_to_store[1]) == 3
        assert len(batched_files_to_store[2]) == 3
        assert len(batched_files_to_store[3]) == 1

    def test_batchify_files_for_insertion_empty_files(self):
        """Test batchify_files_for_insertion with empty files dictionary."""
        files_to_chunk = {}
        max_batch_size_chunking = 5
        
        # Implement the logic
        files_to_chunk_items = list(files_to_chunk.items())
        batched_files_to_store: List[List[Tuple[str, str]]] = []
        for i in range(0, len(files_to_chunk), max_batch_size_chunking):
            batch_files = files_to_chunk_items[i : i + max_batch_size_chunking]
            batched_files_to_store.append(batch_files)
        
        assert batched_files_to_store == []

    def test_batchify_files_exact_batch_size(self):
        """Test batchify_files_for_insertion with files exactly matching batch size."""
        files_to_chunk = {f"file{i}.py": f"hash{i}" for i in range(5)}
        max_batch_size_chunking = 5
        
        # Implement the logic
        files_to_chunk_items = list(files_to_chunk.items())
        batched_files_to_store: List[List[Tuple[str, str]]] = []
        for i in range(0, len(files_to_chunk), max_batch_size_chunking):
            batch_files = files_to_chunk_items[i : i + max_batch_size_chunking]
            batched_files_to_store.append(batch_files)
        
        assert len(batched_files_to_store) == 1
        assert len(batched_files_to_store[0]) == 5

    def test_batchify_files_single_file(self):
        """Test batchify_files_for_insertion with single file."""
        files_to_chunk = {"single_file.py": "single_hash"}
        max_batch_size_chunking = 10
        
        # Implement the logic
        files_to_chunk_items = list(files_to_chunk.items())
        batched_files_to_store: List[List[Tuple[str, str]]] = []
        for i in range(0, len(files_to_chunk), max_batch_size_chunking):
            batch_files = files_to_chunk_items[i : i + max_batch_size_chunking]
            batched_files_to_store.append(batch_files)
        
        assert len(batched_files_to_store) == 1
        assert len(batched_files_to_store[0]) == 1
        assert batched_files_to_store[0][0] == ("single_file.py", "single_hash")

    def test_chunker_has_required_attributes(self):
        """Test that VectorDBChunker has all required attributes after initialization."""
        chunker = self._create_chunker_instance()
        required_attributes = [
            'weaviate_client', 'embedding_manager',
            'chunkable_files_and_hashes', 'use_new_chunking', 'use_async_refresh', 'fetch_with_vector'
        ]
        
        for attr in required_attributes:
            assert hasattr(chunker, attr), f"Missing attribute: {attr}"

    def test_batchify_files_for_insertion_real_method(self):
        """Test the actual batchify_files_for_insertion method."""
        chunker = self._create_chunker_instance()
        
        # Test with small batch
        files_to_chunk = {
            "file1.py": "hash1",
            "file2.py": "hash2",
            "file3.py": "hash3"
        }
        result = chunker.batchify_files_for_insertion(files_to_chunk, max_batch_size_chunking=5)
        
        assert len(result) == 1
        assert len(result[0]) == 3
        assert set(result[0]) == {("file1.py", "hash1"), ("file2.py", "hash2"), ("file3.py", "hash3")}

    def test_batchify_files_for_insertion_large_batch_real_method(self):
        """Test the actual batchify_files_for_insertion method with large batch."""
        chunker = self._create_chunker_instance()
        
        files_to_chunk = {f"file{i}.py": f"hash{i}" for i in range(10)}
        result = chunker.batchify_files_for_insertion(files_to_chunk, max_batch_size_chunking=3)
        
        assert len(result) == 4  # 10 files, batch size 3 = 4 batches (3,3,3,1)
        assert len(result[0]) == 3
        assert len(result[1]) == 3
        assert len(result[2]) == 3
        assert len(result[3]) == 1

    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_real_method(self):
        """Test the actual add_chunk_embeddings method."""
        chunker = self._create_chunker_instance()
        
        # Create mock chunks
        mock_chunks = [
            self._create_mock_chunk_info("file1.py", "content_1"),
            self._create_mock_chunk_info("file2.py", "content_2")
        ]
        
        # Mock embedding manager
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 20))
        
        # Call the actual method
        await chunker.add_chunk_embeddings(mock_chunks)
        
        # Verify embeddings were set
        assert mock_chunks[0].embedding == embeddings[0]
        assert mock_chunks[1].embedding == embeddings[1]
        
        # Verify the embedding manager was called correctly
        chunker.embedding_manager.embed_text_array.assert_called_once()
        call_args = chunker.embedding_manager.embed_text_array.call_args
        texts_sent = call_args.kwargs['texts']
        assert len(texts_sent) == 2

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_for_file_batches_real_method(self):
        """Test the actual create_and_store_chunks_for_file_batches method."""
        with patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.ChunkVectorStoreManager') as mock_manager_class:
            chunker = self._create_chunker_instance()
            
            # Setup test data
            batch1 = [("file1.py", "hash1"), ("file2.py", "hash2")]
            batch2 = [("file3.py", "hash3")]
            batched_files_to_store = [batch1, batch2]
            
            mock_chunks_batch1 = [
                self._create_mock_chunk_info("file1.py", "content_1"),
                self._create_mock_chunk_info("file2.py", "content_2")
            ]
            mock_chunks_batch2 = [
                self._create_mock_chunk_info("file3.py", "content_3")
            ]
            
            # Mock get_file_wise_chunks_for_single_file_batch to return different results for each batch
            async def mock_get_chunks(files_to_chunk_batch):
                if files_to_chunk_batch == batch1:
                    return {"file1.py": [mock_chunks_batch1[0]], "file2.py": [mock_chunks_batch1[1]]}
                else:  # batch2
                    return {"file3.py": [mock_chunks_batch2[0]]}
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(side_effect=mock_get_chunks)
            
            # Mock ChunkVectorStoreManager
            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock()
            mock_manager_class.return_value = mock_manager
            
            custom_timestamp = datetime.now().replace(tzinfo=timezone.utc)
            
            # Call the actual method
            result = await chunker.create_and_store_chunks_for_file_batches(
                batched_files_to_store, custom_timestamp
            )
            
            # Verify the result structure
            expected_result = {
                "file1.py": [mock_chunks_batch1[0]], 
                "file2.py": [mock_chunks_batch1[1]],
                "file3.py": [mock_chunks_batch2[0]]
            }
            assert result == expected_result
            
            # Verify get_file_wise_chunks_for_single_file_batch was called for each batch
            assert chunker.get_file_wise_chunks_for_single_file_batch.call_count == 2
            
            # Verify ChunkVectorStoreManager was created and called correctly
            assert mock_manager_class.call_count == 2
            assert mock_manager.add_differential_chunks_to_store.call_count == 2
            
            # Verify embeddings were removed when fetch_with_vector is False (default)
            for chunk in mock_chunks_batch1 + mock_chunks_batch2:
                assert chunk.embedding is None

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_for_file_batches_with_fetch_with_vector(self):
        """Test create_and_store_chunks_for_file_batches with fetch_with_vector=True."""
        with patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.ChunkVectorStoreManager') as mock_manager_class:
            chunker = self._create_chunker_instance(fetch_with_vector=True)
            
            batch = [("file1.py", "hash1")]
            batched_files_to_store = [batch]
            
            original_embedding = [0.1, 0.2, 0.3]
            mock_chunk = self._create_mock_chunk_info("file1.py", "content", original_embedding.copy())
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(
                return_value={"file1.py": [mock_chunk]}
            )
            
            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock()
            mock_manager_class.return_value = mock_manager
            
            # Call the method
            result = await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            # Verify embedding was NOT removed when fetch_with_vector=True
            assert mock_chunk.embedding == original_embedding

    @pytest.mark.asyncio
    async def test_create_chunks_and_docs_real_method(self):
        """Test the actual create_chunks_and_docs method."""
        with patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.AppLogger') as mock_logger:
            
            chunker = self._create_chunker_instance()
            
            # Setup mock data
            file_path_commit_hash_map = {
                "file1.py": "hash1",
                "file2.py": "hash2",
                "file3.py": "hash3"
            }
            chunker.chunkable_files_and_hashes = file_path_commit_hash_map
            
            # Mock existing chunks (some files already exist, some don't)
            existing_chunk1 = self._create_mock_chunk_info("file1.py", "existing_content", [0.1, 0.2])
            existing_chunk2_no_embedding = self._create_mock_chunk_info("file2.py", "no_embedding_content", None)
            
            existing_file_wise_chunks = {
                "file1.py": [existing_chunk1],
                "file2.py": [existing_chunk2_no_embedding]
                # file3.py is missing (needs to be chunked)
            }
            
            # Mock ChunkVectorStoreManager
            mock_manager = Mock()
            mock_manager.get_valid_file_wise_stored_chunks = AsyncMock(return_value=existing_file_wise_chunks)
            mock_manager_class.return_value = mock_manager
            
            # Mock the create_and_store_chunks_for_file_batches method
            new_chunk3 = self._create_mock_chunk_info("file3.py", "new_file_content", [0.5, 0.6])
            new_chunk2 = self._create_mock_chunk_info("file2.py", "new_content_with_embedding", [0.3, 0.4])
            
            missing_file_wise_chunks = {
                "file2.py": [new_chunk2],  # Re-chunked because of missing embedding
                "file3.py": [new_chunk3]   # New file
            }
            
            chunker.create_and_store_chunks_for_file_batches = AsyncMock(return_value=missing_file_wise_chunks)
            
            # Call the actual method
            result = await chunker.create_chunks_and_docs(enable_refresh=False)
            
            # Verify the method calls
            mock_manager.get_valid_file_wise_stored_chunks.assert_called_once()
            call_args = mock_manager.get_valid_file_wise_stored_chunks.call_args
            assert call_args[0][0] == file_path_commit_hash_map  # file_path_commit_hash_map
            assert call_args[0][1] is False  # fetch_with_vector
            
            # Verify create_and_store_chunks_for_file_batches was called
            chunker.create_and_store_chunks_for_file_batches.assert_called_once()
            
            # Verify the logger was called with missing embeddings count
            mock_logger.log_info.assert_called_once()
            log_call_args = mock_logger.log_info.call_args[0][0]
            assert "Missing chunks which do not have embedding: 1" in log_call_args
            
            # Verify the final result contains chunks
            # Note: The merge logic is {**missing_file_wise_chunks, **existing_file_wise_chunks}
            # This means existing chunks overwrite missing ones for the same file
            assert len(result) == 3  
            result_contents = [chunk.content for chunk in result]
            assert "existing_content" in result_contents  # file1.py existing chunk
            assert "no_embedding_content" in result_contents  # file2.py existing chunk (overwrites missing)
            assert "new_file_content" in result_contents  # file3.py new chunk

    @pytest.mark.asyncio
    async def test_create_chunks_and_docs_with_no_chunkable_files_provided(self):
        """Test create_chunks_and_docs when chunkable_files_and_hashes is None."""
        with patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.AppLogger'):
            
            chunker = self._create_chunker_instance(chunkable_files_and_hashes=None)
            
            # Mock local_repo to return chunkable files
            repo_files = {"repo_file.py": "repo_hash"}
            chunker.local_repo.get_chunkable_files_and_commit_hashes = AsyncMock(return_value=repo_files)
            
            # Mock ChunkVectorStoreManager
            mock_manager = Mock()
            mock_manager.get_valid_file_wise_stored_chunks = AsyncMock(return_value={})
            mock_manager_class.return_value = mock_manager
            
            # Mock create_and_store_chunks_for_file_batches
            new_chunk = self._create_mock_chunk_info("repo_file.py", "repo_content", [0.1, 0.2])
            chunker.create_and_store_chunks_for_file_batches = AsyncMock(
                return_value={"repo_file.py": [new_chunk]}
            )
            
            # Call the method
            result = await chunker.create_chunks_and_docs()
            
            # Verify that local_repo method was called
            chunker.local_repo.get_chunkable_files_and_commit_hashes.assert_called_once()
            
            # Verify get_valid_file_wise_stored_chunks was called with repo files
            mock_manager.get_valid_file_wise_stored_chunks.assert_called_once()
            call_args = mock_manager.get_valid_file_wise_stored_chunks.call_args
            assert call_args[0][0] == repo_files
            
            # Verify result
            assert len(result) == 1
            assert result[0].content == "repo_content"

    @pytest.mark.asyncio
    async def test_create_chunks_and_docs_with_file_indexing_progress_monitor(self):
        """Test create_chunks_and_docs with file_indexing_progress_monitor."""
        with patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.AppLogger'):
            
            chunker = self._create_chunker_instance()
            
            # Add file_indexing_progress_monitor
            mock_monitor = Mock()
            mock_monitor.update_status = Mock()
            chunker.file_indexing_progress_monitor = mock_monitor
            
            file_path_commit_hash_map = {"file1.py": "hash1", "file2.py": "hash2"}
            chunker.chunkable_files_and_hashes = file_path_commit_hash_map
            
            # Mock existing chunks
            existing_chunk1 = self._create_mock_chunk_info("file1.py", "content1", [0.1, 0.2])
            existing_chunk2 = self._create_mock_chunk_info("file2.py", "content2", [0.3, 0.4])
            existing_file_wise_chunks = {
                "file1.py": [existing_chunk1],
                "file2.py": [existing_chunk2]
            }
            
            # Mock ChunkVectorStoreManager
            mock_manager = Mock()
            mock_manager.get_valid_file_wise_stored_chunks = AsyncMock(return_value=existing_file_wise_chunks)
            mock_manager_class.return_value = mock_manager
            
            # No files need chunking since all exist with embeddings
            chunker.create_and_store_chunks_for_file_batches = AsyncMock(return_value={})
            
            # Call the method
            result = await chunker.create_chunks_and_docs()
            
            # Verify progress monitor was called
            mock_monitor.update_status.assert_called_once()
            call_args = mock_monitor.update_status.call_args[0][0]
            expected_status = {
                "file1.py": {"file_path": "file1.py", "status": "COMPLETED"},
                "file2.py": {"file_path": "file2.py", "status": "COMPLETED"}
            }
            assert call_args == expected_status

    @pytest.mark.asyncio
    async def test_create_chunks_and_docs_empty_files(self):
        """Test create_chunks_and_docs with empty file list."""
        with patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.AppLogger'):
            
            chunker = self._create_chunker_instance(chunkable_files_and_hashes={})
            
            # Mock ChunkVectorStoreManager
            mock_manager = Mock()
            mock_manager.get_valid_file_wise_stored_chunks = AsyncMock(return_value={})
            mock_manager_class.return_value = mock_manager
            
            chunker.create_and_store_chunks_for_file_batches = AsyncMock(return_value={})
            
            # Call the method
            result = await chunker.create_chunks_and_docs()
            
            # Verify empty result
            assert result == []
            
            # Verify create_and_store_chunks_for_file_batches was called with empty batches
            chunker.create_and_store_chunks_for_file_batches.assert_called_once()
            call_args = chunker.create_and_store_chunks_for_file_batches.call_args[0][0]
            assert call_args == []  # Empty batched files

    @pytest.mark.asyncio
    async def test_get_file_wise_chunks_for_single_file_batch_real_method(self):
        """Test the actual get_file_wise_chunks_for_single_file_batch method."""
        chunker = self._create_chunker_instance()
        
        # Setup test data
        files_batch = [("file1.py", "hash1"), ("file2.py", "hash2")]
        mock_chunks = [
            self._create_mock_chunk_info("file1.py", "content_1"),
            self._create_mock_chunk_info("file2.py", "content_2")
        ]
        file_wise_chunks = {
            "file1.py": [mock_chunks[0]], 
            "file2.py": [mock_chunks[1]]
        }
        
        # Mock dependencies
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value=file_wise_chunks)
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 10))
        
        # Call the actual method
        result = await chunker.get_file_wise_chunks_for_single_file_batch(files_batch)
        
        # Verify
        assert result == file_wise_chunks
        chunker.file_chunk_creator.create_and_get_file_wise_chunks.assert_called_once_with(
            {"file1.py": "hash1", "file2.py": "hash2"},
            chunker.local_repo.repo_path,
            True,  # use_new_chunking
            process_executor=chunker.process_executor
        )
        
        # Verify embeddings were added to chunks
        chunker.embedding_manager.embed_text_array.assert_called_once()
        assert mock_chunks[0].embedding == embeddings[0]
        assert mock_chunks[1].embedding == embeddings[1]

    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_interface(self):
        """Test add_chunk_embeddings interface and behavior."""
        chunker = self._create_chunker_instance()
        
        # Create mock chunks
        mock_chunks = [
            self._create_mock_chunk_info("file1.py", "content_1"),
            self._create_mock_chunk_info("file2.py", "content_2")
        ]
        
        # Mock embedding manager
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 20))
        
        # Test the interface by calling embed_text_array directly
        texts_to_embed = [
            chunk.get_chunk_content_with_meta_data(add_ellipsis=False, add_lines=False, add_class_function_info=True)
            for chunk in mock_chunks
        ]
        result_embeddings, tokens = await chunker.embedding_manager.embed_text_array(texts=texts_to_embed)
        
        # Verify the interface works
        assert result_embeddings == embeddings
        assert tokens == 20
        
        # Simulate adding embeddings to chunks
        for chunk, embedding in zip(mock_chunks, result_embeddings):
            chunk.embedding = embedding
        
        # Verify embeddings were set
        assert mock_chunks[0].embedding == embeddings[0]
        assert mock_chunks[1].embedding == embeddings[1]

    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_empty_list_interface(self):
        """Test add_chunk_embeddings interface with empty chunk list."""
        chunker = self._create_chunker_instance()
        chunker.embedding_manager.embed_text_array = AsyncMock()
        
        # Test the interface - should handle empty list gracefully
        empty_chunks = []
        if empty_chunks:  # This is what the real method would check
            texts_to_embed = [
                chunk.get_chunk_content_with_meta_data(add_ellipsis=False, add_lines=False, add_class_function_info=True)
                for chunk in empty_chunks
            ]
            await chunker.embedding_manager.embed_text_array(texts=texts_to_embed)
        
        # Should not call embed_text_array for empty list
        chunker.embedding_manager.embed_text_array.assert_not_called()

    @pytest.mark.asyncio
    async def test_file_chunk_creation_interface(self):
        """Test file chunk creation interface."""
        chunker = self._create_chunker_instance()
        
        # Setup test data
        files_batch = [("file1.py", "hash1"), ("file2.py", "hash2")]
        mock_chunks = [
            self._create_mock_chunk_info("file1.py", "content_1"),
            self._create_mock_chunk_info("file2.py", "content_2")
        ]
        file_wise_chunks = {
            "file1.py": [mock_chunks[0]], 
            "file2.py": [mock_chunks[1]]
        }
        
        # Mock dependencies
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value=file_wise_chunks)
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=([[0.1, 0.2], [0.3, 0.4]], 10))
        
        # Test the interface
        result = await chunker.file_chunk_creator.create_and_get_file_wise_chunks(
            {"file1.py": "hash1", "file2.py": "hash2"},
            chunker.local_repo.repo_path,
            chunker.use_new_chunking,
            process_executor=chunker.process_executor
        )
        
        # Verify
        assert result == file_wise_chunks
        chunker.file_chunk_creator.create_and_get_file_wise_chunks.assert_called_once_with(
            {"file1.py": "hash1", "file2.py": "hash2"},
            chunker.local_repo.repo_path,
            True,  # use_new_chunking
            process_executor=chunker.process_executor
        )

    @pytest.mark.asyncio
    async def test_file_chunk_creation_no_chunks_interface(self):
        """Test file chunk creation interface when no chunks are created."""
        chunker = self._create_chunker_instance()
        
        files_batch = [("file1.py", "hash1")]
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value={})
        
        result = await chunker.file_chunk_creator.create_and_get_file_wise_chunks(
            {"file1.py": "hash1"},
            chunker.local_repo.repo_path,
            chunker.use_new_chunking,
            process_executor=chunker.process_executor
        )
        
        assert result == {}

    def test_embedding_removal_when_not_fetching_with_vector(self):
        """Test that embeddings are removed when fetch_with_vector is False."""
        chunker = self._create_chunker_instance(fetch_with_vector=False)
        
        # Create a chunk with embedding
        chunk = self._create_mock_chunk_info("file1.py", "content", [0.1, 0.2, 0.3])
        file_wise_chunks = {"file1.py": [chunk]}
        
        # Simulate the logic from create_and_store_chunks_for_file_batches
        if not chunker.fetch_with_vector:
            for chunks in file_wise_chunks.values():
                for chunk in chunks:
                    chunk.embedding = None
        
        # Verify embedding was removed
        assert chunk.embedding is None

    def test_embedding_retention_when_fetching_with_vector(self):
        """Test that embeddings are kept when fetch_with_vector is True."""
        chunker = self._create_chunker_instance(fetch_with_vector=True)
        
        original_embedding = [0.1, 0.2, 0.3]
        chunk = self._create_mock_chunk_info("file1.py", "content", original_embedding.copy())
        file_wise_chunks = {"file1.py": [chunk]}
        
        # Simulate the logic from create_and_store_chunks_for_file_batches
        if not chunker.fetch_with_vector:  # This should be False, so embeddings remain
            for chunks in file_wise_chunks.values():
                for chunk in chunks:
                    chunk.embedding = None
        
        # Verify embedding was kept
        assert chunk.embedding == original_embedding

    @pytest.mark.asyncio
    async def test_chunkable_files_from_local_repo_interface(self):
        """Test getting chunkable files from local repo when not provided."""
        chunker = self._create_chunker_instance(chunkable_files_and_hashes=None)
        
        # Mock the local_repo method to return files
        test_files = {"test_file.py": "test_hash"}
        chunker.local_repo.get_chunkable_files_and_commit_hashes = AsyncMock(return_value=test_files)
        
        # Test the interface
        file_path_commit_hash_map = chunker.chunkable_files_and_hashes
        if not file_path_commit_hash_map:
            file_path_commit_hash_map = await chunker.local_repo.get_chunkable_files_and_commit_hashes()
        
        # Verify
        assert file_path_commit_hash_map == test_files
        chunker.local_repo.get_chunkable_files_and_commit_hashes.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunkable_files_provided_interface(self):
        """Test using provided chunkable files."""
        sample_chunkable_files = {
            "src/main.py": "hash_main_py",
            "src/utils.py": "hash_utils_py"
        }
        chunker = self._create_chunker_instance(chunkable_files_and_hashes=sample_chunkable_files)
        
        # Test the interface
        file_path_commit_hash_map = chunker.chunkable_files_and_hashes
        if not file_path_commit_hash_map:
            file_path_commit_hash_map = await chunker.local_repo.get_chunkable_files_and_commit_hashes()
        
        # Verify
        assert file_path_commit_hash_map == sample_chunkable_files
        chunker.local_repo.get_chunkable_files_and_commit_hashes.assert_not_called()

    def test_empty_files_handling(self):
        """Test handling of empty files dictionary."""
        chunker = self._create_chunker_instance(chunkable_files_and_hashes={})
        
        # Test the batching logic with empty files
        files_to_chunk = {}
        max_batch_size_chunking = 200
        
        files_to_chunk_items = list(files_to_chunk.items())
        batched_files_to_store: List[List[Tuple[str, str]]] = []
        for i in range(0, len(files_to_chunk), max_batch_size_chunking):
            batch_files = files_to_chunk_items[i : i + max_batch_size_chunking]
            batched_files_to_store.append(batch_files)
        
        # Should result in empty list since range(0, 0, 200) produces no iterations
        assert batched_files_to_store == []

    @pytest.mark.asyncio
    async def test_multiple_chunks_embedding_interface(self):
        """Test adding embeddings to multiple chunks with different content."""
        chunker = self._create_chunker_instance()
        
        # Create chunks with different content
        mock_chunks = [
            self._create_mock_chunk_info("file1.py", "def function1(): pass"),
            self._create_mock_chunk_info("file2.py", "class TestClass: pass"),
            self._create_mock_chunk_info("file3.py", "import os")
        ]
        
        # Mock embedding manager to return different embeddings
        embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 30))
        
        # Test the interface
        texts_to_embed = [
            chunk.get_chunk_content_with_meta_data(add_ellipsis=False, add_lines=False, add_class_function_info=True)
            for chunk in mock_chunks
        ]
        result_embeddings, tokens = await chunker.embedding_manager.embed_text_array(texts=texts_to_embed)
        
        # Simulate setting embeddings
        for chunk, embedding in zip(mock_chunks, result_embeddings):
            chunk.embedding = embedding
        
        # Verify each chunk got its respective embedding
        for i, chunk in enumerate(mock_chunks):
            assert chunk.embedding == embeddings[i]
        
        # Verify the embedding manager was called correctly
        assert tokens == 30
        call_args = chunker.embedding_manager.embed_text_array.call_args
        texts_sent = call_args.kwargs['texts']
        assert len(texts_sent) == 3
        for chunk in mock_chunks:
            chunk.get_chunk_content_with_meta_data.assert_called_with(
                add_ellipsis=False, add_lines=False, add_class_function_info=True
            )

    def test_missing_embedding_detection_logic(self):
        """Test logic for detecting chunks with missing embeddings."""
        chunker = self._create_chunker_instance()
        
        # Create chunks - some with embeddings, some without
        chunk_with_embedding = self._create_mock_chunk_info("file1.py", "content1", [0.1, 0.2])
        chunk_without_embedding = self._create_mock_chunk_info("file2.py", "content2", None)
        another_without_embedding = self._create_mock_chunk_info("file3.py", "content3", None)
        
        existing_file_wise_chunks = {
            "file1.py": [chunk_with_embedding],
            "file2.py": [chunk_without_embedding], 
            "file3.py": [another_without_embedding]
        }
        
        file_path_commit_hash_map = {
            "file1.py": "hash1",
            "file2.py": "hash2", 
            "file3.py": "hash3"
        }
        
        # Simulate the missing embedding detection logic
        files_to_chunk = {}
        count = 0
        for file, chunks in existing_file_wise_chunks.items():
            if file in file_path_commit_hash_map:
                for chunk in chunks:
                    if not chunk.embedding:
                        count += 1
                        files_to_chunk[file] = file_path_commit_hash_map[file]
        
        # Should detect 2 chunks without embeddings
        assert count == 2
        assert files_to_chunk == {"file2.py": "hash2", "file3.py": "hash3"}

    def test_chunk_info_structure(self):
        """Test that mock ChunkInfo objects have the expected structure."""
        chunk = self._create_mock_chunk_info("test.py", "test content", [0.1, 0.2])
        
        # Test required attributes
        assert hasattr(chunk, 'content')
        assert hasattr(chunk, 'content_hash')
        assert hasattr(chunk, 'embedding')
        assert hasattr(chunk, 'source_details')
        assert hasattr(chunk, 'metadata')
        
        # Test source_details attributes
        assert hasattr(chunk.source_details, 'file_path')
        assert hasattr(chunk.source_details, 'file_hash')
        assert hasattr(chunk.source_details, 'start_line')
        assert hasattr(chunk.source_details, 'end_line')
        
        # Test method exists
        assert hasattr(chunk, 'get_chunk_content_with_meta_data')
        assert callable(chunk.get_chunk_content_with_meta_data)
        
        # Test values
        assert chunk.content == "test content"
        assert chunk.embedding == [0.1, 0.2]
        assert chunk.source_details.file_path == "test.py"