"""
Unit tests for VectorDBChunker class.

This module contains comprehensive test cases for the VectorDBChunker,
covering initialization, chunking operations, batch processing, and vector store integration.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import sys

import pytest


# Since conftest.py aggressively mocks modules, we need to work around it
class TestVectorDBChunker:
    """Test cases for VectorDBChunker class."""

    def setup_method(self):
        """Setup method to ensure clean mocking for each test."""
        # Clear any existing modules that might interfere
        modules_to_clear = [
            'deputydev_core.services.chunking.chunker.handlers.vector_db_chunker',
        ]
        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]

    def _create_mock_chunk(self, content="def sample_function():\n    return 'test'", file_path="test.py", start_line=1, end_line=2, file_hash="test_hash", embedding=None):
        """Create a properly structured mock chunk for testing."""
        chunk = Mock()
        
        # Mock source_details
        chunk.source_details = Mock()
        chunk.source_details.file_path = file_path
        chunk.source_details.start_line = start_line
        chunk.source_details.end_line = end_line
        chunk.source_details.file_hash = file_hash
        
        # Mock basic properties
        chunk.content = content
        chunk.content_hash = f"hash_{hash(content) % 10000}"
        chunk.embedding = embedding
        chunk.has_embedded_lines = False
        chunk.search_score = 0
        
        # Create a proper metadata structure that matches ChunkMetadata expectations
        chunk.metadata = Mock()
        chunk.metadata.hierarchy = []  # Empty list for iteration
        chunk.metadata.dechunk = False
        chunk.metadata.import_only_chunk = False
        chunk.metadata.all_functions = []
        chunk.metadata.all_classes = []
        chunk.metadata.byte_size = len(content.encode('utf-8'))
        
        # Mock methods
        chunk.get_chunk_content_with_meta_data = Mock(return_value=f"<meta_data>File path: {file_path}</meta_data>\n<code>\n{content}\n</code>")
        
        return chunk

    def _create_chunker_with_mocks(self, **kwargs):
        """Create a VectorDBChunker instance with properly mocked dependencies."""
        # Create a mock BaseChunker class that actually sets attributes and doesn't interfere
        class MockBaseChunker:
            def __init__(self, local_repo, process_executor):
                self.local_repo = local_repo
                self.process_executor = process_executor
                self.file_chunk_creator = Mock()

        # Temporarily remove modules from sys.modules to prevent interference
        original_modules = {}
        modules_to_patch = [
            'deputydev_core.services.chunking.chunker.handlers.vector_db_chunker',
            'deputydev_core.services.chunking.chunker.base_chunker'
        ]
        
        for module in modules_to_patch:
            if module in sys.modules:
                original_modules[module] = sys.modules[module]
                del sys.modules[module]
        
        try:
            # Mock all the imports and dependencies
            mock_chunk_vector_store_manager = Mock()
            mock_chunk_vector_store_manager_instance = Mock()
            mock_chunk_vector_store_manager_instance.get_valid_file_wise_stored_chunks = AsyncMock(return_value={})
            mock_chunk_vector_store_manager_instance.add_differential_chunks_to_store = AsyncMock()
            mock_chunk_vector_store_manager.return_value = mock_chunk_vector_store_manager_instance
            
            with patch.dict('sys.modules', {
                'deputydev_core.services.chunking.source_chunker': Mock(),
                'tree_sitter_language_pack': Mock(),
            }):
                with patch.multiple(
                    'deputydev_core.services.chunking.chunker.handlers.vector_db_chunker',
                    BaseChunker=MockBaseChunker,
                    ChunkVectorStoreManager=mock_chunk_vector_store_manager,
                    RefreshConfig=Mock(),
                    AppLogger=Mock(),
                ):
                    from deputydev_core.services.chunking.chunker.handlers.vector_db_chunker import VectorDBChunker
                    
                    # Create default kwargs with properly mocked weaviate client
                    mock_weaviate_client = Mock()
                    mock_weaviate_client.sync_client = Mock()
                    mock_weaviate_client.async_client = Mock()
                    mock_weaviate_client.async_client.ensure_connected = AsyncMock()
                    
                    default_kwargs = {
                        'local_repo': Mock(),
                        'process_executor': Mock(),
                        'weaviate_client': mock_weaviate_client,
                        'embedding_manager': Mock(),
                    }
                    default_kwargs.update(kwargs)
                    
                    chunker = VectorDBChunker(**default_kwargs)
                    # Store the mock manager instance for test access
                    chunker._mock_chunk_vector_store_manager = mock_chunk_vector_store_manager_instance
                    
                    # Ensure the chunker has the file_chunk_creator properly set as a Mock with async methods
                    if not hasattr(chunker, 'file_chunk_creator') or chunker.file_chunk_creator is None:
                        chunker.file_chunk_creator = Mock()
                    
                    # Ensure create_and_get_file_wise_chunks is an AsyncMock
                    if hasattr(chunker.file_chunk_creator, 'create_and_get_file_wise_chunks'):
                        if not hasattr(chunker.file_chunk_creator.create_and_get_file_wise_chunks, 'assert_not_called'):
                            chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock()
                    else:
                        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock()
                    
                    return chunker
        finally:
            # Restore original modules
            for module, original in original_modules.items():
                sys.modules[module] = original

    def test_initialization_with_default_parameters(self):
        """Test VectorDBChunker initialization with default parameters."""
        chunker = self._create_chunker_with_mocks()
        
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
        chunker = self._create_chunker_with_mocks(
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
        chunker = self._create_chunker_with_mocks()
        files_to_chunk = {
            "file1.py": "hash1",
            "file2.py": "hash2",
            "file3.py": "hash3"
        }
        
        result = chunker.batchify_files_for_insertion(files_to_chunk, max_batch_size_chunking=5)
        
        assert len(result) == 1
        assert len(result[0]) == 3
        assert result[0] == [("file1.py", "hash1"), ("file2.py", "hash2"), ("file3.py", "hash3")]

    def test_batchify_files_for_insertion_large_batch(self):
        """Test batchify_files_for_insertion with files more than batch size."""
        chunker = self._create_chunker_with_mocks()
        files_to_chunk = {f"file{i}.py": f"hash{i}" for i in range(10)}
        
        result = chunker.batchify_files_for_insertion(files_to_chunk, max_batch_size_chunking=3)
        
        assert len(result) == 4  # 10 files, batch size 3 = 4 batches (3,3,3,1)
        assert len(result[0]) == 3
        assert len(result[1]) == 3
        assert len(result[2]) == 3
        assert len(result[3]) == 1

    def test_batchify_files_for_insertion_empty_files(self):
        """Test batchify_files_for_insertion with empty files dictionary."""
        chunker = self._create_chunker_with_mocks()
        result = chunker.batchify_files_for_insertion({})
        
        assert result == []

    def test_batchify_files_exact_batch_size(self):
        """Test batchify_files_for_insertion with files exactly matching batch size."""
        chunker = self._create_chunker_with_mocks()
        files_to_chunk = {f"file{i}.py": f"hash{i}" for i in range(5)}
        
        result = chunker.batchify_files_for_insertion(files_to_chunk, max_batch_size_chunking=5)
        
        assert len(result) == 1
        assert len(result[0]) == 5

    def test_batchify_files_single_file(self):
        """Test batchify_files_for_insertion with single file."""
        chunker = self._create_chunker_with_mocks()
        files_to_chunk = {"single_file.py": "single_hash"}
        
        result = chunker.batchify_files_for_insertion(files_to_chunk, max_batch_size_chunking=10)
        
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == ("single_file.py", "single_hash")

    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_success(self):
        """Test successful addition of embeddings to chunks."""
        chunker = self._create_chunker_with_mocks()
        
        # Create properly structured mock chunks
        mock_chunks = [
            self._create_mock_chunk("content_0", "file_0.py"),
            self._create_mock_chunk("content_1", "file_1.py")
        ]
        
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=(embeddings, 20))
        
        # Execute
        await chunker.add_chunk_embeddings(mock_chunks)
        
        # Verify
        chunker.embedding_manager.embed_text_array.assert_called_once()
        assert mock_chunks[0].embedding == embeddings[0]
        assert mock_chunks[1].embedding == embeddings[1]

    @pytest.mark.asyncio
    async def test_add_chunk_embeddings_empty_list(self):
        """Test adding embeddings to empty chunk list."""
        chunker = self._create_chunker_with_mocks()
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=([], 0))
        
        await chunker.add_chunk_embeddings([])
        
        chunker.embedding_manager.embed_text_array.assert_called_once_with(texts=[])

    @pytest.mark.asyncio
    async def test_get_file_wise_chunks_for_single_file_batch_success(self):
        """Test successful processing of file batch for chunks."""
        chunker = self._create_chunker_with_mocks()
        
        # Setup
        files_batch = [("file1.py", "hash1"), ("file2.py", "hash2")]
        mock_chunks = [Mock(), Mock()]
        file_wise_chunks = {
            "file1.py": [mock_chunks[0]], 
            "file2.py": [mock_chunks[1]]
        }
        
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value=file_wise_chunks)
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=([[0.1, 0.2]], 10))
        
        # Execute
        result = await chunker.get_file_wise_chunks_for_single_file_batch(files_batch)
        
        # Verify
        chunker.file_chunk_creator.create_and_get_file_wise_chunks.assert_called_once_with(
            {"file1.py": "hash1", "file2.py": "hash2"},
            chunker.local_repo.repo_path,
            True,  # use_new_chunking
            process_executor=chunker.process_executor
        )
        assert result == file_wise_chunks

    @pytest.mark.asyncio
    async def test_get_file_wise_chunks_for_single_file_batch_no_chunks(self):
        """Test processing file batch when no chunks are created."""
        chunker = self._create_chunker_with_mocks()
        
        files_batch = [("file1.py", "hash1")]
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value={})
        chunker.embedding_manager.embed_text_array = AsyncMock()
        
        result = await chunker.get_file_wise_chunks_for_single_file_batch(files_batch)
        
        assert result == {}
        # Embedding manager should not be called for empty chunks
        chunker.embedding_manager.embed_text_array.assert_not_called()

    @pytest.mark.asyncio 
    async def test_create_and_store_chunks_for_file_batches_success(self):
        """Test successful creation and storage of chunks for file batches."""
        chunker = self._create_chunker_with_mocks()
        
        # Setup - Create properly structured mock chunks
        mock_chunk_1 = self._create_mock_chunk("content_1", "file1.py", file_hash="hash1", embedding=[0.1, 0.2])
        mock_chunk_2 = self._create_mock_chunk("content_2", "file2.py", file_hash="hash2", embedding=[0.3, 0.4])
        
        # Set metadata to None to avoid Pydantic validation issues in ChunkVectorStoreManager
        mock_chunk_1.metadata = None
        mock_chunk_2.metadata = None
            
        batched_files = [
            [("file1.py", "hash1")],
            [("file2.py", "hash2")]
        ]
        file_wise_chunks_batch1 = {"file1.py": [mock_chunk_1]}
        file_wise_chunks_batch2 = {"file2.py": [mock_chunk_2]}
        
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock()
        chunker.file_chunk_creator.create_and_get_file_wise_chunks.side_effect = [
            file_wise_chunks_batch1,
            file_wise_chunks_batch2
        ]
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=([[0.1, 0.2]], 10))
        
        # Execute - Use the pre-configured mock ChunkVectorStoreManager
        result = await chunker.create_and_store_chunks_for_file_batches(batched_files)
        
        # Verify
        expected_result = {**file_wise_chunks_batch1, **file_wise_chunks_batch2}
        assert result == expected_result
        
        # Verify ChunkVectorStoreManager was called for each batch
        assert chunker._mock_chunk_vector_store_manager.add_differential_chunks_to_store.call_count == 2

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_removes_embeddings_when_not_fetching_with_vector(self):
        """Test that embeddings are removed when fetch_with_vector is False."""
        chunker = self._create_chunker_with_mocks(fetch_with_vector=False)
        
        batched_files = [[("file1.py", "hash1")]]
        chunk = self._create_mock_chunk("test content", "file1.py", file_hash="hash1", embedding=[0.1, 0.2, 0.3])
        chunk.metadata = None  # Set to None to avoid Pydantic validation issues
        file_wise_chunks = {"file1.py": [chunk]}
        
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value=file_wise_chunks)
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=([[0.1, 0.2]], 10))
        
        # Execute using pre-configured mock
        await chunker.create_and_store_chunks_for_file_batches(batched_files)
        
        # Verify embedding was removed
        assert chunk.embedding is None

    @pytest.mark.asyncio
    async def test_create_and_store_chunks_keeps_embeddings_when_fetching_with_vector(self):
        """Test that embeddings are kept when fetch_with_vector is True."""
        chunker = self._create_chunker_with_mocks(fetch_with_vector=True)
        
        batched_files = [[("file1.py", "hash1")]]
        original_embedding = [0.1, 0.2, 0.3]
        chunk = self._create_mock_chunk("test content", "file1.py", file_hash="hash1", embedding=original_embedding)
        chunk.metadata = None  # Set to None to avoid Pydantic validation issues
        file_wise_chunks = {"file1.py": [chunk]}
        
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value=file_wise_chunks)
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=([original_embedding], 10))
        
        # Execute using pre-configured mock
        await chunker.create_and_store_chunks_for_file_batches(batched_files)
        
        # Verify embedding was kept
        assert chunk.embedding == original_embedding

    @pytest.mark.asyncio
    async def test_create_chunks_and_docs_with_existing_chunkable_files(self):
        """Test create_chunks_and_docs when chunkable_files_and_hashes is provided."""
        sample_chunkable_files = {
            "src/main.py": "hash_main_py",
            "src/utils.py": "hash_utils_py"
        }
        chunker = self._create_chunker_with_mocks(chunkable_files_and_hashes=sample_chunkable_files)
        
        # Setup - Create properly structured mock chunks
        existing_chunk = self._create_mock_chunk("existing content", "src/main.py", file_hash="hash_main_py", embedding=[0.1, 0.2, 0.3])
        new_chunk = self._create_mock_chunk("new content", "src/utils.py", file_hash="hash_utils_py", embedding=None)
        existing_chunk.metadata = None  # Set to None to avoid validation issues
        new_chunk.metadata = None
        
        existing_chunks = {"src/main.py": [existing_chunk]}
        new_chunks = {"src/utils.py": [new_chunk]}
        
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value=new_chunks)
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=([[0.1, 0.2]], 10))
        
        # Mock the local_repo method
        chunker.local_repo.get_chunkable_files_and_commit_hashes = AsyncMock()
        
        # Configure the pre-mocked ChunkVectorStoreManager
        chunker._mock_chunk_vector_store_manager.get_valid_file_wise_stored_chunks.return_value = existing_chunks
        
        # Execute
        result = await chunker.create_chunks_and_docs()
        
        # Verify
        assert len(result) == 2  # One existing chunk + one new chunk
        chunker.local_repo.get_chunkable_files_and_commit_hashes.assert_not_called()  # Should not be called when files are provided
        chunker._mock_chunk_vector_store_manager.get_valid_file_wise_stored_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_chunks_and_docs_empty_files(self):
        """Test create_chunks_and_docs with no files to process."""
        chunker = self._create_chunker_with_mocks(chunkable_files_and_hashes={})
        
        # Mock the local_repo method - since chunkable_files_and_hashes is empty dict, 
        # it should still be used and not call the async method
        chunker.local_repo.get_chunkable_files_and_commit_hashes = AsyncMock(return_value={})
        
        with patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.ChunkVectorStoreManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.get_valid_file_wise_stored_chunks = AsyncMock(return_value={})
            mock_manager_class.return_value = mock_manager
            
            # Execute
            result = await chunker.create_chunks_and_docs()
            
            # Verify
            assert result == []
            # Should not try to create chunks for empty file list
            chunker.file_chunk_creator.create_and_get_file_wise_chunks.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_chunks_and_docs_when_chunkable_files_is_none(self):
        """Test create_chunks_and_docs when chunkable_files_and_hashes is None."""
        chunker = self._create_chunker_with_mocks(chunkable_files_and_hashes=None)
        
        # Mock the local_repo method to return empty dict
        chunker.local_repo.get_chunkable_files_and_commit_hashes = AsyncMock(return_value={})
        
        with patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.ChunkVectorStoreManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.get_valid_file_wise_stored_chunks = AsyncMock(return_value={})
            mock_manager_class.return_value = mock_manager
            
            # Execute
            result = await chunker.create_chunks_and_docs()
            
            # Verify
            assert result == []
            # Should call get_chunkable_files_and_commit_hashes when chunkable_files_and_hashes is None
            chunker.local_repo.get_chunkable_files_and_commit_hashes.assert_called_once()

    def test_chunker_has_create_chunks_and_docs_method(self):
        """Test that VectorDBChunker has the required create_chunks_and_docs method."""
        chunker = self._create_chunker_with_mocks()
        assert hasattr(chunker, 'create_chunks_and_docs')
        assert callable(chunker.create_chunks_and_docs)

    def test_chunker_has_required_attributes(self):
        """Test that VectorDBChunker has all required attributes after initialization."""
        chunker = self._create_chunker_with_mocks()
        required_attributes = [
            'weaviate_client', 'embedding_manager',
            'chunkable_files_and_hashes', 'use_new_chunking', 'use_async_refresh', 'fetch_with_vector'
        ]
        
        for attr in required_attributes:
            assert hasattr(chunker, attr), f"Missing attribute: {attr}"

    @pytest.mark.asyncio
    async def test_create_chunks_and_docs_with_missing_embeddings(self):
        """Test create_chunks_and_docs handles chunks with missing embeddings."""
        sample_chunkable_files = {"src/main.py": "hash_main_py"}
        chunker = self._create_chunker_with_mocks(chunkable_files_and_hashes=sample_chunkable_files)
        
        # Setup - Create properly structured mock chunk
        chunk_without_embedding = self._create_mock_chunk("test content", "src/main.py", file_hash="hash_main_py", embedding=None)
        chunk_without_embedding.metadata = None  # Set to None to avoid validation issues
        existing_chunks = {"src/main.py": [chunk_without_embedding]}
        
        chunker.file_chunk_creator.create_and_get_file_wise_chunks = AsyncMock(return_value={"src/main.py": [chunk_without_embedding]})
        chunker.embedding_manager.embed_text_array = AsyncMock(return_value=([[0.1, 0.2]], 10))
        
        # Mock the local_repo method
        chunker.local_repo.get_chunkable_files_and_commit_hashes = AsyncMock()
        
        # Configure the pre-mocked ChunkVectorStoreManager
        chunker._mock_chunk_vector_store_manager.get_valid_file_wise_stored_chunks.return_value = existing_chunks
        
        with patch('deputydev_core.services.chunking.chunker.handlers.vector_db_chunker.AppLogger') as mock_logger:
            # Execute
            result = await chunker.create_chunks_and_docs()
            
            # Verify
            # Should log missing embeddings
            mock_logger.log_info.assert_called_with("Missing chunks which do not have embedding: 1")
            # Should re-process the file with missing embeddings
            assert len(result) >= 1