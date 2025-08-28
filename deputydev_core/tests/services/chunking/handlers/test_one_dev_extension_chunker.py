"""
Unit tests for OneDevExtensionChunker class.

This module contains comprehensive unit tests for the OneDevExtensionChunker,
testing each method in isolation while following .deputydevrules guidelines.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import sys

import pytest

# Mock tree_sitter_language_pack at module level to avoid import errors
sys.modules['tree_sitter_language_pack'] = MagicMock()


def force_real_import():
    """Force import of real OneDevExtensionChunker class by bypassing mocks."""
    # Store original sys.modules state
    original_modules = {}
    modules_to_patch = [
        'deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker',
        'deputydev_core.services.chunking.chunker.handlers.vector_db_chunker',
        'deputydev_core.services.chunking.chunker.base_chunker',
    ]
    
    for module_name in modules_to_patch:
        if module_name in sys.modules:
            original_modules[module_name] = sys.modules[module_name]
            del sys.modules[module_name]
    
    try:
        # Import the real modules
        from deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker import OneDevExtensionChunker
        return OneDevExtensionChunker
    finally:
        # Don't restore the mocks - let the real modules stay
        pass


class TestOneDevExtensionChunker:
    """Unit test cases for OneDevExtensionChunker class."""

    def setup_method(self):
        """Setup method to ensure clean mocking for each test."""
        # Always get a fresh import of the real class
        self.OneDevExtensionChunker = force_real_import()

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
        """Create a OneDevExtensionChunker instance with fully mocked dependencies."""
        
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
            'indexing_progress_bar': None,
            'embedding_progress_bar': None,
            'use_new_chunking': True,
            'use_async_refresh': True,
            'fetch_with_vector': False,
            'file_indexing_progress_monitor': None,
        }
        default_kwargs.update(kwargs)
        
        # Create a real OneDevExtensionChunker instance
        chunker = self.OneDevExtensionChunker(**default_kwargs)
        
        # Mock the file_chunk_creator which is set in the parent class
        mock_file_chunk_creator = Mock()
        mock_file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value={})
        chunker.file_chunk_creator = mock_file_chunk_creator
        
        return chunker

    # Unit Tests for Initialization
    def test_initialization_with_default_parameters(self):
        """Test OneDevExtensionChunker initialization with default parameters."""
        chunker = self._create_chunker_instance()
        
        # Test that the OneDevExtensionChunker-specific attributes are properly set
        assert hasattr(chunker, 'embedding_manager')
        assert hasattr(chunker, 'indexing_progress_bar')
        assert hasattr(chunker, 'embedding_progress_bar')
        assert hasattr(chunker, 'file_indexing_progress_monitor')
        
        # Test inherited VectorDBChunker attributes
        assert hasattr(chunker, 'weaviate_client')
        assert hasattr(chunker, 'use_new_chunking')
        assert hasattr(chunker, 'use_async_refresh')
        assert hasattr(chunker, 'fetch_with_vector')
        assert hasattr(chunker, 'chunkable_files_and_hashes')
        
        # Test default values for OneDevExtensionChunker specific attributes
        assert chunker.indexing_progress_bar is None
        assert chunker.embedding_progress_bar is None
        assert chunker.file_indexing_progress_monitor is None
        
        # Test inherited default values
        assert chunker.chunkable_files_and_hashes is None
        assert chunker.use_new_chunking is True
        assert chunker.use_async_refresh is True  # Different from VectorDBChunker default
        assert chunker.fetch_with_vector is False

    def test_initialization_with_custom_parameters(self):
        """Test OneDevExtensionChunker initialization with custom parameters."""
        mock_indexing_progress = Mock()
        mock_embedding_progress = Mock()
        mock_monitor = Mock()
        custom_files = {"file1.py": "hash1", "file2.py": "hash2"}
        
        chunker = self._create_chunker_instance(
            chunkable_files_and_hashes=custom_files,
            indexing_progress_bar=mock_indexing_progress,
            embedding_progress_bar=mock_embedding_progress,
            use_new_chunking=False,
            use_async_refresh=False,
            fetch_with_vector=True,
            file_indexing_progress_monitor=mock_monitor
        )
        
        # Test OneDevExtensionChunker specific attributes
        assert chunker.indexing_progress_bar is mock_indexing_progress
        assert chunker.embedding_progress_bar is mock_embedding_progress
        assert chunker.file_indexing_progress_monitor is mock_monitor
        
        # Test inherited attributes
        assert chunker.chunkable_files_and_hashes == custom_files
        assert chunker.use_new_chunking is False
        assert chunker.use_async_refresh is False
        assert chunker.fetch_with_vector is True

    def test_chunker_has_required_attributes_from_parent(self):
        """Test that OneDevExtensionChunker inherits all required attributes from VectorDBChunker."""
        chunker = self._create_chunker_instance()
        
        # Test parent class attributes
        required_parent_attributes = [
            'weaviate_client', 'embedding_manager',
            'chunkable_files_and_hashes', 'use_new_chunking', 
            'use_async_refresh', 'fetch_with_vector'
        ]
        
        # Test OneDevExtensionChunker specific attributes
        required_child_attributes = [
            'indexing_progress_bar', 'embedding_progress_bar', 
            'file_indexing_progress_monitor'
        ]
        
        for attr in required_parent_attributes + required_child_attributes:
            assert hasattr(chunker, attr), f"Missing attribute: {attr}"

    # Unit Tests for get_file_wise_chunks_for_single_file_batch
    @pytest.mark.asyncio
    async def test_get_file_wise_chunks_for_single_file_batch_basic(self):
        """Test get_file_wise_chunks_for_single_file_batch with basic functionality."""
        chunker = self._create_chunker_instance()
        
        # Setup test data
        files_batch = [("file1.py", "hash1"), ("file2.py", "hash2")]
        mock_chunks = [
            self._create_mock_chunk_info("file1.py", "content_1"),
            self._create_mock_chunk_info("file2.py", "content_2")
        ]
        expected_result = {
            "file1.py": [mock_chunks[0]], 
            "file2.py": [mock_chunks[1]]
        }
        
        # Mock file_chunk_creator
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(
            return_value=expected_result
        )
        
        # Call the method
        result = await chunker.get_file_wise_chunks_for_single_file_batch(files_batch)
        
        # Verify result
        assert result == expected_result
        
        # Verify the file_chunk_creator was called correctly
        chunker.file_chunk_creator.create_and_get_file_wise_chunks.assert_called_once_with(
            {"file1.py": "hash1", "file2.py": "hash2"},
            chunker.local_repo.repo_path,
            chunker.use_new_chunking,
            process_executor=chunker.process_executor,
            set_config_in_new_process=True,
            progress_bar=chunker.indexing_progress_bar,
            files_indexing_monitor=chunker.file_indexing_progress_monitor,
        )

    @pytest.mark.asyncio
    async def test_get_file_wise_chunks_for_single_file_batch_with_progress_bars(self):
        """Test get_file_wise_chunks_for_single_file_batch with progress bars."""
        mock_indexing_progress = Mock()
        mock_monitor = Mock()
        
        chunker = self._create_chunker_instance(
            indexing_progress_bar=mock_indexing_progress,
            file_indexing_progress_monitor=mock_monitor
        )
        
        files_batch = [("file1.py", "hash1")]
        expected_result = {"file1.py": [self._create_mock_chunk_info("file1.py", "content")]}
        
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(
            return_value=expected_result
        )
        
        result = await chunker.get_file_wise_chunks_for_single_file_batch(files_batch)
        
        # Verify that progress bar and monitor are passed correctly
        call_args = chunker.file_chunk_creator.create_and_get_file_wise_chunks.call_args
        assert call_args.kwargs['progress_bar'] is mock_indexing_progress
        assert call_args.kwargs['files_indexing_monitor'] is mock_monitor
        assert call_args.kwargs['set_config_in_new_process'] is True

    @pytest.mark.asyncio
    async def test_get_file_wise_chunks_for_single_file_batch_empty_batch(self):
        """Test get_file_wise_chunks_for_single_file_batch with empty batch."""
        chunker = self._create_chunker_instance()
        
        files_batch = []
        expected_result = {}
        
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(
            return_value=expected_result
        )
        
        result = await chunker.get_file_wise_chunks_for_single_file_batch(files_batch)
        
        assert result == expected_result
        
        # Verify empty dict is passed to file_chunk_creator
        call_args = chunker.file_chunk_creator.create_and_get_file_wise_chunks.call_args
        assert call_args[0][0] == {}  # Empty dict from dict(files_batch)

    @pytest.mark.asyncio
    async def test_get_file_wise_chunks_for_single_file_batch_use_new_chunking_false(self):
        """Test get_file_wise_chunks_for_single_file_batch with use_new_chunking=False."""
        chunker = self._create_chunker_instance(use_new_chunking=False)
        
        files_batch = [("file1.py", "hash1")]
        expected_result = {"file1.py": [self._create_mock_chunk_info("file1.py", "content")]}
        
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(
            return_value=expected_result
        )
        
        result = await chunker.get_file_wise_chunks_for_single_file_batch(files_batch)
        
        # Verify use_new_chunking=False is passed
        call_args = chunker.file_chunk_creator.create_and_get_file_wise_chunks.call_args
        assert call_args[0][2] is False  # use_new_chunking parameter

    # Unit Tests for update_embeddings
    @pytest.mark.asyncio
    async def test_update_embeddings_basic(self):
        """Test update_embeddings with basic functionality."""
        chunker = self._create_chunker_instance()
        
        # Create test chunks
        chunk1 = self._create_mock_chunk_info("file1.py", "content1")
        chunk2 = self._create_mock_chunk_info("file2.py", "content2")
        file_wise_chunks = {
            "file1.py": [chunk1],
            "file2.py": [chunk2]
        }
        
        # Mock add_chunk_embeddings method
        chunker.add_chunk_embeddings = AsyncMock(return_value=None)
        
        # Call the method
        await chunker.update_embeddings(file_wise_chunks)
        
        # Verify add_chunk_embeddings was called with flattened chunks
        chunker.add_chunk_embeddings.assert_called_once()
        call_args = chunker.add_chunk_embeddings.call_args[0][0]
        assert len(call_args) == 2
        assert chunk1 in call_args
        assert chunk2 in call_args

    @pytest.mark.asyncio
    async def test_update_embeddings_empty_chunks(self):
        """Test update_embeddings with empty file_wise_chunks."""
        chunker = self._create_chunker_instance()
        
        file_wise_chunks = {}
        chunker.add_chunk_embeddings = AsyncMock(return_value=None)

        await chunker.update_embeddings(file_wise_chunks)
        
        # Should not call add_chunk_embeddings for empty chunks
        chunker.add_chunk_embeddings.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_embeddings_multiple_chunks_per_file(self):
        """Test update_embeddings with multiple chunks per file."""
        chunker = self._create_chunker_instance()
        
        # Create test data with multiple chunks per file
        chunk1 = self._create_mock_chunk_info("file1.py", "content1")
        chunk2 = self._create_mock_chunk_info("file1.py", "content2")
        chunk3 = self._create_mock_chunk_info("file2.py", "content3")
        
        file_wise_chunks = {
            "file1.py": [chunk1, chunk2],
            "file2.py": [chunk3]
        }
        
        chunker.add_chunk_embeddings = AsyncMock(return_value=None)

        await chunker.update_embeddings(file_wise_chunks)
        
        # Verify all chunks are flattened and passed
        call_args = chunker.add_chunk_embeddings.call_args[0][0]
        assert len(call_args) == 3
        assert chunk1 in call_args
        assert chunk2 in call_args
        assert chunk3 in call_args

    @pytest.mark.asyncio
    async def test_update_embeddings_single_file_multiple_chunks(self):
        """Test update_embeddings with single file containing multiple chunks."""
        chunker = self._create_chunker_instance()
        
        chunks = [
            self._create_mock_chunk_info("file1.py", f"content_{i}") 
            for i in range(5)
        ]
        file_wise_chunks = {"file1.py": chunks}
        
        chunker.add_chunk_embeddings = AsyncMock(return_value=None)

        await chunker.update_embeddings(file_wise_chunks)
        
        # Verify all chunks from single file are included
        call_args = chunker.add_chunk_embeddings.call_args[0][0]
        assert len(call_args) == 5
        for chunk in chunks:
            assert chunk in call_args

    # Unit Tests for create_and_store_chunks_for_file_batches
    @pytest.mark.asyncio
    async def test_create_and_store_chunks_for_file_batches_basic(self):
        """Test create_and_store_chunks_for_file_batches with basic functionality."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task') as mock_create_task:
            
            chunker = self._create_chunker_instance()
            
            # Setup test data
            batch1 = [("file1.py", "hash1"), ("file2.py", "hash2")]
            batch2 = [("file3.py", "hash3")]
            batched_files_to_store = [batch1, batch2]
            
            # Create mock chunks
            mock_chunks_batch1 = {
                "file1.py": [self._create_mock_chunk_info("file1.py", "content1")],
                "file2.py": [self._create_mock_chunk_info("file2.py", "content2")]
            }
            mock_chunks_batch2 = {
                "file3.py": [self._create_mock_chunk_info("file3.py", "content3")]
            }
            
            # Mock methods
            async def mock_get_chunks(files_to_chunk_batch):
                if files_to_chunk_batch == batch1:
                    return mock_chunks_batch1
                else:
                    return mock_chunks_batch2
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(side_effect=mock_get_chunks)
            chunker.update_embeddings = AsyncMock(return_value=None)
            chunker._monitor_embedding_tasks = AsyncMock(return_value=None)
            
            # Mock ChunkVectorStoreManager
            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager
            
            # Mock embedding task monitoring
            mock_task = Mock()
            mock_task.done.return_value = True
            mock_create_task.return_value = mock_task
            
            custom_timestamp = datetime.now().replace(tzinfo=timezone.utc)
            
            # Call the method
            result = await chunker.create_and_store_chunks_for_file_batches(
                batched_files_to_store, custom_timestamp
            )
            
            # Verify result structure
            expected_result = {**mock_chunks_batch1, **mock_chunks_batch2}
            assert result == expected_result
            
            # Verify get_file_wise_chunks_for_single_file_batch called for each batch
            assert chunker.get_file_wise_chunks_for_single_file_batch.call_count == 2
            
            # Verify ChunkVectorStoreManager was created and called correctly
            assert mock_manager_class.call_count == 2
            assert mock_manager.add_differential_chunks_to_store.call_count == 2
            
            # Verify update_embeddings was called for each batch
            assert chunker.update_embeddings.call_count == 2

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_for_file_batches_with_progress_bars(self):
        """Test create_and_store_chunks_for_file_batches with progress bars."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task') as mock_create_task:
            
            # Setup mock methods for progress bars
            mock_indexing_progress.initialise = Mock()
            mock_indexing_progress.set_current_batch_percentage = Mock()
            mock_indexing_progress.mark_finish = Mock()
            
            mock_embedding_progress.initialise = Mock()
            mock_embedding_progress.set_current_batch_percentage = Mock()
            mock_embedding_progress.mark_finish = Mock()
            
            chunker = self._create_chunker_instance(
                indexing_progress_bar=mock_indexing_progress,
                embedding_progress_bar=mock_embedding_progress
            )
            
            # Setup test data
            batch1 = [("file1.py", "hash1"), ("file2.py", "hash2")]
            batched_files_to_store = [batch1]
            
            mock_chunks = {
                "file1.py": [self._create_mock_chunk_info("file1.py", "content1")]
            }
            
            # Mock methods
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(return_value=mock_chunks)
            chunker.update_embeddings = AsyncMock(return_value=None)
            chunker._monitor_embedding_tasks = AsyncMock(return_value=None)
            
            # Mock ChunkVectorStoreManager
            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager
            
            # Call the method
            await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            # Verify progress bar initialization
            mock_indexing_progress.initialise.assert_called_once_with(total_files_to_process=2)
            mock_embedding_progress.initialise.assert_called_once_with(total_files_to_process=2)
            
            # Verify progress bar updates
            mock_indexing_progress.set_current_batch_percentage.assert_called_once_with(2)
            mock_embedding_progress.set_current_batch_percentage.assert_called_once_with(2)
            
            # Verify progress bar finish
            mock_indexing_progress.mark_finish.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_for_file_batches_with_progress_bars(self):
        """Test create_and_store_chunks_for_file_batches with progress bars."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task') as mock_create_task:
            
            # Create chunker without progress bars (default None values)
            chunker = self._create_chunker_instance()
            
            batch1 = [("file1.py", "hash1")]
            batched_files_to_store = [batch1]
            
            mock_chunks = {"file1.py": [self._create_mock_chunk_info("file1.py", "content1")]}
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(return_value=mock_chunks)
            chunker.update_embeddings = AsyncMock(return_value=None)
            chunker._monitor_embedding_tasks = AsyncMock(return_value=None)

            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager
            
            # Should not raise any exceptions with None progress bars
            result = await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            # Verify result
            assert result == mock_chunks

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_for_file_batches_embedding_removal(self):
        """Test create_and_store_chunks_for_file_batches removes embeddings when fetch_with_vector=False."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task'):
            
            chunker = self._create_chunker_instance(fetch_with_vector=False)
            
            batch1 = [("file1.py", "hash1")]
            batched_files_to_store = [batch1]
            
            # Create chunk with initial embedding
            chunk_with_embedding = self._create_mock_chunk_info("file1.py", "content1", [0.1, 0.2, 0.3])
            mock_chunks = {"file1.py": [chunk_with_embedding]}
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(return_value=mock_chunks)
            chunker.update_embeddings = AsyncMock(return_value=None)
            chunker._monitor_embedding_tasks = AsyncMock(return_value=None)

            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager
            
            # Call the method
            result = await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            # Verify embedding was removed (set to None)
            assert chunk_with_embedding.embedding is None

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_for_file_batches_embedding_retention(self):
        """Test create_and_store_chunks_for_file_batches keeps embeddings when fetch_with_vector=True."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task'):
            
            chunker = self._create_chunker_instance(fetch_with_vector=True)
            
            batch1 = [("file1.py", "hash1")]
            batched_files_to_store = [batch1]
            
            # Create chunk with initial embedding
            original_embedding = [0.1, 0.2, 0.3]
            chunk_with_embedding = self._create_mock_chunk_info("file1.py", "content1", original_embedding.copy())
            mock_chunks = {"file1.py": [chunk_with_embedding]}
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(return_value=mock_chunks)
            chunker.update_embeddings = AsyncMock(return_value=None)
            chunker._monitor_embedding_tasks = AsyncMock(return_value=None)

            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager
            
            # Call the method
            result = await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            # Verify embedding was kept
            assert chunk_with_embedding.embedding == original_embedding

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_for_file_batches_empty_batches(self):
        """Test create_and_store_chunks_for_file_batches with empty batches."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task'):
            
            chunker = self._create_chunker_instance()
            
            # Empty batches
            batched_files_to_store = []
            
            # Call the method
            result = await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            # Should return empty dict
            assert result == {}

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_for_file_batches_custom_timestamp(self):
        """Test create_and_store_chunks_for_file_batches with custom timestamp."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task'):
            
            chunker = self._create_chunker_instance()
            
            batch1 = [("file1.py", "hash1")]
            batched_files_to_store = [batch1]
            custom_timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            
            mock_chunks = {"file1.py": [self._create_mock_chunk_info("file1.py", "content1")]}
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(return_value=mock_chunks)
            chunker.update_embeddings = AsyncMock(return_value=None)
            chunker._monitor_embedding_tasks = AsyncMock(return_value=None)

            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager
            
            # Call the method with custom timestamp
            await chunker.create_and_store_chunks_for_file_batches(
                batched_files_to_store, 
                custom_timestamp=custom_timestamp
            )
            
            # Verify custom timestamp was passed to add_differential_chunks_to_store
            call_args = mock_manager.add_differential_chunks_to_store.call_args
            assert call_args.kwargs['custom_create_timestamp'] == custom_timestamp
            assert call_args.kwargs['custom_update_timestamp'] == custom_timestamp

    # Unit Tests for _monitor_embedding_tasks
    @pytest.mark.asyncio
    async def test_monitor_embedding_tasks_all_done(self):
        """Test _monitor_embedding_tasks when all tasks are done immediately."""
        chunker = self._create_chunker_instance()
        
        # Create mock tasks that are already done
        mock_task1 = Mock()
        mock_task1.done.return_value = True
        mock_task2 = Mock()
        mock_task2.done.return_value = True
        
        tasks = [mock_task1, mock_task2]
        
        mock_embedding_progress = Mock()
        mock_embedding_progress.mark_finish = Mock()
        
        # Call the method
        await chunker._monitor_embedding_tasks(tasks, mock_embedding_progress)
        
        # Verify mark_finish was called
        mock_embedding_progress.mark_finish.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_embedding_tasks_with_delay(self):
        """Test _monitor_embedding_tasks when tasks complete after some delay."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            chunker = self._create_chunker_instance()
            
            # Create mock tasks that complete after one check
            mock_task = Mock()
            # First call returns False, second call returns True
            mock_task.done.side_effect = [False, True]
            
            tasks = [mock_task]
            
            mock_embedding_progress = Mock()
            mock_embedding_progress.mark_finish = Mock()
            
            # Call the method
            await chunker._monitor_embedding_tasks(tasks, mock_embedding_progress)
            
            # Verify sleep was called once (for the False case)
            mock_sleep.assert_called_once_with(0.5)
            
            # Verify mark_finish was called
            mock_embedding_progress.mark_finish.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_embedding_tasks_none_progress_bar(self):
        """Test _monitor_embedding_tasks with None progress bar."""
        chunker = self._create_chunker_instance()
        
        # Create mock task that is done
        mock_task = Mock()
        mock_task.done.return_value = True
        
        tasks = [mock_task]
        
        # The actual implementation has a bug - it tries to call mark_finish() on None
        # This test verifies the current behavior (which will raise AttributeError)
        with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'mark_finish'"):
            await chunker._monitor_embedding_tasks(tasks, None)

    # Unit Tests for add_chunk_embeddings  
    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_basic(self):
        """Test add_chunk_embeddings with basic functionality."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkService') as mock_chunk_service_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.gather', new_callable=AsyncMock) as mock_gather:
            
            chunker = self._create_chunker_instance()
            
            # Create mock chunks
            chunk1 = self._create_mock_chunk_info("file1.py", "content1")
            chunk2 = self._create_mock_chunk_info("file2.py", "content2")
            chunks = [chunk1, chunk2]
            
            # Mock embedding manager
            embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 20))
            
            # Mock ChunkService
            mock_chunk_service = Mock()
            mock_chunk_service.update_embedding = AsyncMock(return_value=None)
            mock_chunk_service_class.return_value = mock_chunk_service
            
            # Call the method
            await chunker.add_chunk_embeddings(chunks)
            
            # Verify embeddings were set on chunks
            assert chunk1.embedding == embeddings[0]
            assert chunk2.embedding == embeddings[1]
            
            # Verify embed_text_array was called correctly
            call_args = chunker.embedding_manager.embed_text_array.call_args
            texts_sent = call_args.kwargs['texts']
            assert len(texts_sent) == 2
            
            # Verify progress bar was passed
            assert call_args.kwargs['progress_bar_counter'] == chunker.embedding_progress_bar
            
            # Verify ChunkService was created and update_embedding was called for each chunk
            mock_chunk_service_class.assert_called_once_with(weaviate_client=chunker.weaviate_client)
            assert mock_chunk_service.update_embedding.call_count == 2

    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_batch_processing(self):
        """Test add_chunk_embeddings with batch processing of updates."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkService') as mock_chunk_service_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.gather', new_callable=AsyncMock) as mock_gather:
            
            chunker = self._create_chunker_instance()
            
            # Create 15 mock chunks to test batching (batch size is 10)
            chunks = [
                self._create_mock_chunk_info(f"file{i}.py", f"content{i}")
                for i in range(15)
            ]
            
            # Mock embedding manager
            embeddings = [[0.1 * i, 0.2 * i, 0.3 * i] for i in range(15)]
            chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 100))
            
            # Mock ChunkService
            mock_chunk_service = Mock()
            mock_chunk_service.update_embedding = AsyncMock(return_value=None)
            mock_chunk_service_class.return_value = mock_chunk_service
            
            # Call the method
            await chunker.add_chunk_embeddings(chunks)
            
            # Verify embeddings were set on all chunks
            for i, chunk in enumerate(chunks):
                assert chunk.embedding == embeddings[i]
            
            # Verify gather was called twice (once for first 10 chunks, once for remaining 5)
            assert mock_gather.call_count == 2
            
            # Verify update_embedding was called for all chunks
            assert mock_chunk_service.update_embedding.call_count == 15

    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_empty_chunks(self):
        """Test add_chunk_embeddings with empty chunks list."""
        chunker = self._create_chunker_instance()
        
        # Mock embedding manager to return empty results for empty input
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=([], 0))
        
        # Call the method with empty list - should handle gracefully
        await chunker.add_chunk_embeddings([])
        
        # Verify embedding manager was called with empty list
        chunker.embedding_manager.embed_text_array.assert_called_once_with(
            texts=[], progress_bar_counter=chunker.embedding_progress_bar
        )

    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_with_embedding_progress_bar(self):
        """Test add_chunk_embeddings with embedding progress bar."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkService') as mock_chunk_service_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.gather', new_callable=AsyncMock):
            
            mock_embedding_progress = Mock()
            chunker = self._create_chunker_instance(embedding_progress_bar=mock_embedding_progress)
            
            chunks = [self._create_mock_chunk_info("file1.py", "content1")]
            embeddings = [[0.1, 0.2, 0.3]]
            chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 10))
            
            mock_chunk_service = Mock()
            mock_chunk_service.update_embedding = AsyncMock(return_value=None)
            mock_chunk_service_class.return_value = mock_chunk_service
            
            await chunker.add_chunk_embeddings(chunks)
            
            # Verify progress bar was passed to embed_text_array
            call_args = chunker.embedding_manager.embed_text_array.call_args
            assert call_args.kwargs['progress_bar_counter'] is mock_embedding_progress

    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_chunk_content_formatting(self):
        """Test add_chunk_embeddings calls get_chunk_content_with_meta_data correctly."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkService') as mock_chunk_service_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.gather', new_callable=AsyncMock):
            
            chunker = self._create_chunker_instance()
            
            chunk = self._create_mock_chunk_info("file1.py", "content1")
            chunks = [chunk]
            
            embeddings = [[0.1, 0.2, 0.3]]
            chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 10))
            
            mock_chunk_service = Mock()
            mock_chunk_service.update_embedding = AsyncMock(return_value=None)
            mock_chunk_service_class.return_value = mock_chunk_service
            
            await chunker.add_chunk_embeddings(chunks)
            
            # Verify get_chunk_content_with_meta_data was called with correct parameters
            chunk.get_chunk_content_with_meta_data.assert_called_once_with(
                add_ellipsis=False,
                add_lines=False,
                add_class_function_info=True
            )

    # Integration Tests
    @pytest.mark.asyncio
    async def test_integration_create_and_store_with_embedding_updates(self):
        """Integration test: create_and_store_chunks_for_file_batches with embedding updates."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkService') as mock_chunk_service_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task') as mock_create_task, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.gather', new_callable=AsyncMock):
            
            chunker = self._create_chunker_instance()
            
            # Setup test data
            batch = [("file1.py", "hash1")]
            batched_files_to_store = [batch]
            
            # Create mock chunks
            chunk1 = self._create_mock_chunk_info("file1.py", "content1")
            file_wise_chunks = {"file1.py": [chunk1]}
            
            # Mock the chunking step
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(return_value=file_wise_chunks)
            
            # Mock the embedding step
            embeddings = [[0.1, 0.2, 0.3]]
            chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 10))
            
            # Mock ChunkVectorStoreManager
            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager

            # Mock ChunkService
            mock_chunk_service = Mock()
            mock_chunk_service.update_embedding = AsyncMock(return_value=None)
            mock_chunk_service_class.return_value = mock_chunk_service
            
            # Mock _monitor_embedding_tasks to avoid unawaited coroutine warnings
            chunker._monitor_embedding_tasks = AsyncMock(return_value=None)
            
            # Mock task creation for embedding monitoring
            mock_task = Mock()
            mock_task.done.return_value = True
            mock_create_task.return_value = mock_task
            
            # Call the main method
            result = await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            # Verify the full flow
            assert result == file_wise_chunks
            
            # Verify chunking was called with correct parameter name
            chunker.get_file_wise_chunks_for_single_file_batch.assert_called_once_with(files_to_chunk_batch=batch)
            
            # Verify vector store was called
            mock_manager.add_differential_chunks_to_store.assert_called_once()
            
            # Verify embedding tasks were created
            mock_create_task.assert_called()

    def test_inheritance_structure(self):
        """Test that OneDevExtensionChunker properly inherits from VectorDBChunker."""
        chunker = self._create_chunker_instance()
        
        # Test inheritance
        from deputydev_core.services.chunking.chunker.handlers.vector_db_chunker import VectorDBChunker
        assert isinstance(chunker, VectorDBChunker)
        
        # Test that parent methods are available
        assert hasattr(chunker, 'batchify_files_for_insertion')
        assert callable(chunker.batchify_files_for_insertion)

    def test_method_override_behavior(self):
        """Test that OneDevExtensionChunker properly overrides parent methods."""
        chunker = self._create_chunker_instance()
        
        # Test that specific methods exist and are callable
        assert hasattr(chunker, 'get_file_wise_chunks_for_single_file_batch')
        assert callable(chunker.get_file_wise_chunks_for_single_file_batch)
        
        assert hasattr(chunker, 'create_and_store_chunks_for_file_batches')
        assert callable(chunker.create_and_store_chunks_for_file_batches)
        
        assert hasattr(chunker, 'update_embeddings')
        assert callable(chunker.update_embeddings)
        
        assert hasattr(chunker, 'add_chunk_embeddings')
        assert callable(chunker.add_chunk_embeddings)

    def test_docstring_presence(self):
        """Test that key methods have docstrings."""
        chunker = self._create_chunker_instance()
        
        # Check docstrings exist for main methods
        assert chunker.get_file_wise_chunks_for_single_file_batch.__doc__ is not None
        assert chunker.create_and_store_chunks_for_file_batches.__doc__ is not None
        assert chunker.add_chunk_embeddings.__doc__ is not None
        
        # Check that docstrings contain meaningful content
        create_method_doc = chunker.create_and_store_chunks_for_file_batches.__doc__
        assert "Creates and stores chunks" in create_method_doc
        assert "Args:" in create_method_doc
        assert "Returns:" in create_method_doc

    # Edge Cases and Error Handling
    @pytest.mark.asyncio
    async def test_create_and_store_chunks_none_custom_timestamp(self):
        """Test create_and_store_chunks_for_file_batches with None custom_timestamp."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task'):
            
            chunker = self._create_chunker_instance()
            
            batch = [("file1.py", "hash1")]
            batched_files_to_store = [batch]
            
            mock_chunks = {"file1.py": [self._create_mock_chunk_info("file1.py", "content1")]}
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(return_value=mock_chunks)
            chunker.update_embeddings = AsyncMock(return_value=None)
            chunker._monitor_embedding_tasks = AsyncMock(return_value=None)

            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager
            
            # Call with None timestamp (default behavior)
            await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            # Verify None timestamp was passed
            call_args = mock_manager.add_differential_chunks_to_store.call_args
            assert call_args.kwargs['custom_create_timestamp'] is None
            assert call_args.kwargs['custom_update_timestamp'] is None

    @pytest.mark.asyncio
    async def test_edge_case_single_batch_single_file(self):
        """Test edge case: single batch with single file."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task'):
            
            chunker = self._create_chunker_instance()
            
            # Single batch, single file
            batch = [("single_file.py", "single_hash")]
            batched_files_to_store = [batch]
            
            mock_chunks = {"single_file.py": [self._create_mock_chunk_info("single_file.py", "content")]}
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(return_value=mock_chunks)
            chunker.update_embeddings = AsyncMock(return_value=None)
            chunker._monitor_embedding_tasks = AsyncMock(return_value=None)
            
            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager
            
            
            result = await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            assert result == mock_chunks
            assert len(result) == 1
            assert "single_file.py" in result

    @pytest.mark.asyncio  
    async def test_edge_case_large_number_of_batches(self):
        """Test edge case: large number of small batches."""
        with patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.ChunkVectorStoreManager') as mock_manager_class, \
             patch('deputydev_core.services.chunking.chunker.handlers.one_dev_extension_chunker.asyncio.create_task'):
            
            chunker = self._create_chunker_instance()
            
            # Create 100 small batches
            batched_files_to_store = [[(f"file_{i}.py", f"hash_{i}")] for i in range(100)]
            
            # Mock responses for each batch
            async def mock_get_chunks(files_to_chunk_batch):
                file_path = files_to_chunk_batch[0][0]  # Get file path from batch
                return {file_path: [self._create_mock_chunk_info(file_path, f"content_{file_path}")]}
            
            chunker.get_file_wise_chunks_for_single_file_batch = AsyncMock(side_effect=mock_get_chunks)
            chunker.update_embeddings = AsyncMock(return_value=None)
            
            mock_manager = Mock()
            mock_manager.add_differential_chunks_to_store = AsyncMock(return_value=None)
            mock_manager_class.return_value = mock_manager
            
            result = await chunker.create_and_store_chunks_for_file_batches(batched_files_to_store)
            
            # Verify all files were processed
            assert len(result) == 100
            for i in range(100):
                assert f"file_{i}.py" in result
            
            # Verify methods were called the correct number of times
            assert chunker.get_file_wise_chunks_for_single_file_batch.call_count == 100
            assert chunker.update_embeddings.call_count == 100
            assert mock_manager.add_differential_chunks_to_store.call_count == 100

    def test_parameter_validation_types(self):
        """Test that the class properly handles different parameter types."""
        # Test with different embedding manager types
        mock_extension_manager = Mock()
        mock_pr_review_manager = Mock()
        
        # Should work with ExtensionEmbeddingManager type
        chunker1 = self._create_chunker_instance(embedding_manager=mock_extension_manager)
        assert chunker1.embedding_manager is mock_extension_manager
        
        # Should work with PRReviewEmbeddingManager type  
        chunker2 = self._create_chunker_instance(embedding_manager=mock_pr_review_manager)
        assert chunker2.embedding_manager is mock_pr_review_manager

    def test_attribute_access_patterns(self):
        """Test various attribute access patterns."""
        mock_progress = Mock()
        mock_monitor = Mock()
        
        chunker = self._create_chunker_instance(
            indexing_progress_bar=mock_progress,
            embedding_progress_bar=mock_progress,
            file_indexing_progress_monitor=mock_monitor
        )
        
        # Test direct attribute access
        assert chunker.indexing_progress_bar is mock_progress
        assert chunker.embedding_progress_bar is mock_progress
        assert chunker.file_indexing_progress_monitor is mock_monitor
        
        # Test that attributes can be set to None
        chunker.indexing_progress_bar = None
        assert chunker.indexing_progress_bar is None