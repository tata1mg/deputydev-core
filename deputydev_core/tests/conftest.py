"""
Pytest configuration and shared fixtures for DeputyDev Core test suite.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List
from unittest.mock import Mock
import sys

import pytest

# Mock problematic imports before they're imported
sys.modules['tree_sitter_language_pack'] = Mock()
sys.modules['deputydev_core.services.chunking.source_chunker'] = Mock()
sys.modules['deputydev_core.services.chunking.chunker.base_chunker'] = Mock()

try:
    from weaviate import WeaviateAsyncClient, WeaviateClient
except ImportError:
    WeaviateAsyncClient = Mock
    WeaviateClient = Mock

# Define mock classes for consistent use across all tests
class MockChunkSourceDetails:
    def __init__(self, file_path, start_line, end_line, file_hash=None):
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.file_hash = file_hash

class MockChunkMetadata:
    def __init__(self):
        self.hierarchy = []
        self.all_classes = []
        self.all_functions = []

class MockChunkInfo:
    def __init__(self, content, file_path, start_line, end_line, file_hash=None, embedding=None, metadata=None):
        self.content = content
        self.source_details = MockChunkSourceDetails(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            file_hash=file_hash
        )
        self.embedding = embedding
        self.metadata = metadata or MockChunkMetadata()
        self.has_embedded_lines = False
        self.search_score = 0
    
    @property
    def content_hash(self):
        # Simple hash for testing
        return f"hash_{hash(self.content) % 10000}"
    
    @property
    def file_path(self):
        return self.source_details.file_path
    
    @property
    def start_line(self):
        return self.source_details.start_line
    
    @property
    def end_line(self):
        return self.source_details.end_line
    
    @property
    def file_hash(self):
        return self.source_details.file_hash

class MockWeaviateSyncAndAsyncClients:
    def __init__(self, sync_client=None, async_client=None):
        self.sync_client = sync_client or Mock()
        self.async_client = async_client or Mock()

# Use our mock classes consistently
ChunkInfo = MockChunkInfo
ChunkSourceDetails = MockChunkSourceDetails
ChunkMetadata = MockChunkMetadata
WeaviateSyncAndAsyncClients = MockWeaviateSyncAndAsyncClients

# Try to import other modules, but fall back to mocks
try:
    from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
except ImportError:
    OneDevClient = Mock

try:
    from deputydev_core.services.embedding.extension_embedding_manager import (
        ExtensionEmbeddingManager,
    )
except ImportError:
    ExtensionEmbeddingManager = Mock

try:
    from deputydev_core.services.embedding.pr_review_embedding_manager import (
        PRReviewEmbeddingManager,
    )
except ImportError:
    PRReviewEmbeddingManager = Mock

try:
    from deputydev_core.services.repo.local_repo.base_local_repo_service import (
        BaseLocalRepo,
    )
except ImportError:
    BaseLocalRepo = Mock

try:
    from deputydev_core.utils.custom_progress_bar import CustomProgressBar
except ImportError:
    CustomProgressBar = Mock

try:
    from deputydev_core.utils.file_indexing_monitor import FileIndexingMonitor
except ImportError:
    FileIndexingMonitor = Mock


# Pytest Configuration
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# Event Loop Fixture
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Mock Client Fixtures
@pytest.fixture
def mock_weaviate_sync_client():
    """Create a mock Weaviate sync client."""
    return Mock(spec=WeaviateClient)


@pytest.fixture
def mock_weaviate_async_client():
    """Create a mock Weaviate async client."""
    return Mock(spec=WeaviateAsyncClient)


@pytest.fixture
def mock_weaviate_clients(mock_weaviate_sync_client, mock_weaviate_async_client):
    """Create mock Weaviate sync and async clients."""
    return WeaviateSyncAndAsyncClients(
        sync_client=mock_weaviate_sync_client,
        async_client=mock_weaviate_async_client
    )


@pytest.fixture
def mock_one_dev_client():
    """Create a mock OneDevClient."""
    return Mock(spec=OneDevClient)


@pytest.fixture
def mock_process_executor():
    """Create a mock ProcessPoolExecutor."""
    return Mock(spec=ProcessPoolExecutor)


# Repository Fixtures
@pytest.fixture
def mock_local_repo():
    """Create a mock BaseLocalRepo."""
    repo = Mock(spec=BaseLocalRepo)
    repo.repo_path = "/test/repo/path"
    repo.get_chunkable_files_and_commit_hashes = Mock(return_value={})
    return repo


# Embedding Manager Fixtures
@pytest.fixture
def mock_extension_embedding_manager():
    """Create a mock ExtensionEmbeddingManager."""
    return Mock(spec=ExtensionEmbeddingManager)


@pytest.fixture
def mock_pr_review_embedding_manager():
    """Create a mock PRReviewEmbeddingManager."""
    return Mock(spec=PRReviewEmbeddingManager)


# Progress Bar and Monitor Fixtures
@pytest.fixture
def mock_indexing_progress_bar():
    """Create a mock CustomProgressBar for indexing."""
    return Mock(spec=CustomProgressBar)


@pytest.fixture
def mock_embedding_progress_bar():
    """Create a mock CustomProgressBar for embedding."""
    return Mock(spec=CustomProgressBar)


@pytest.fixture
def mock_file_indexing_monitor():
    """Create a mock FileIndexingMonitor."""
    return Mock(spec=FileIndexingMonitor)


# Data Fixtures
@pytest.fixture
def sample_chunkable_files() -> Dict[str, str]:
    """Sample dictionary of chunkable files and their hashes."""
    return {
        "src/main.py": "hash_main_py",
        "src/utils.py": "hash_utils_py", 
        "src/models/user.py": "hash_user_py",
        "tests/test_main.py": "hash_test_main_py",
        "docs/README.md": "hash_readme_md"
    }


@pytest.fixture
def sample_chunk_info() -> MockChunkInfo:
    """Create a sample ChunkInfo object."""
    return MockChunkInfo(
        content="def sample_function():\n    return 'Hello, World!'",
        file_path="src/sample.py",
        start_line=1,
        end_line=2,
        file_hash="sample_file_hash",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5]
    )


@pytest.fixture
def sample_chunk_info_list(sample_chunkable_files) -> List[MockChunkInfo]:
    """Create a list of sample ChunkInfo objects."""
    chunks = []
    
    # Create chunks for each file
    file_paths = list(sample_chunkable_files.keys())
    file_hashes = list(sample_chunkable_files.values())
    
    for i, (file_path, file_hash) in enumerate(zip(file_paths, file_hashes)):
        chunk = MockChunkInfo(
            content=f"# Content for {file_path}\ndef function_{i}():\n    pass",
            file_path=file_path,
            start_line=1,
            end_line=3,
            file_hash=file_hash,
            embedding=[0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i, 0.5 * i] if i % 2 == 0 else None
        )
        chunks.append(chunk)
    
    return chunks


@pytest.fixture
def sample_chunk_info_with_missing_embeddings(sample_chunk_info_list) -> List[MockChunkInfo]:
    """Create a list of ChunkInfo objects where some have missing embeddings."""
    # Modify some chunks to have missing embeddings
    modified_chunks = []
    for i, chunk in enumerate(sample_chunk_info_list):
        if i % 3 == 0:  # Every third chunk has no embedding
            modified_chunk = MockChunkInfo(
                content=chunk.content,
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                file_hash=chunk.file_hash,
                embedding=None
            )
            modified_chunks.append(modified_chunk)
        else:
            modified_chunks.append(chunk)
    
    return modified_chunks


@pytest.fixture
def empty_chunkable_files() -> Dict[str, str]:
    """Empty dictionary of chunkable files."""
    return {}


@pytest.fixture
def empty_chunk_info_list() -> List[MockChunkInfo]:
    """Empty list of ChunkInfo objects."""
    return []


# File-wise chunks fixture for testing existing chunks scenarios
@pytest.fixture
def sample_existing_file_wise_chunks(sample_chunk_info_list) -> Dict[str, List[MockChunkInfo]]:
    """Sample existing file-wise chunks for testing."""
    file_wise_chunks = {}
    
    for chunk in sample_chunk_info_list[:3]:  # Use first 3 chunks
        if chunk.file_path not in file_wise_chunks:
            file_wise_chunks[chunk.file_path] = []
        file_wise_chunks[chunk.file_path].append(chunk)
    
    return file_wise_chunks


# Test utilities
@pytest.fixture
def assert_chunk_equality():
    """Utility function to assert ChunkInfo equality."""
    def _assert_chunk_equality(chunk1: ChunkInfo, chunk2: ChunkInfo):
        """Assert that two ChunkInfo objects are equal."""
        assert chunk1.content == chunk2.content
        assert chunk1.content_hash == chunk2.content_hash
        assert chunk1.file_path == chunk2.file_path
        assert chunk1.start_line == chunk2.start_line
        assert chunk1.end_line == chunk2.end_line
        assert chunk1.file_hash == chunk2.file_hash
        assert chunk1.embedding == chunk2.embedding
    
    return _assert_chunk_equality


@pytest.fixture
def assert_chunks_list_equality():
    """Utility function to assert ChunkInfo list equality."""
    def _assert_chunks_list_equality(chunks1: List[ChunkInfo], chunks2: List[ChunkInfo]):
        """Assert that two lists of ChunkInfo objects are equal."""
        assert len(chunks1) == len(chunks2)
        
        # Sort both lists by content_hash for consistent comparison
        sorted_chunks1 = sorted(chunks1, key=lambda x: x.content_hash)
        sorted_chunks2 = sorted(chunks2, key=lambda x: x.content_hash)
        
        for chunk1, chunk2 in zip(sorted_chunks1, sorted_chunks2):
            assert chunk1.content == chunk2.content
            assert chunk1.content_hash == chunk2.content_hash
            assert chunk1.file_path == chunk2.file_path
            assert chunk1.start_line == chunk2.start_line
            assert chunk1.end_line == chunk2.end_line
            assert chunk1.file_hash == chunk2.file_hash
            assert chunk1.embedding == chunk2.embedding
    
    return _assert_chunks_list_equality


# Mock factory fixtures for complex scenarios
@pytest.fixture
def mock_chunk_info_factory():
    """Factory for creating mock ChunkInfo objects with custom parameters."""
    def _create_chunk_info(
        content: str = "default content",
        file_path: str = "default.py",
        start_line: int = 1,
        end_line: int = 1,
        file_hash: str = "default_file_hash",
        embedding: List[float] = None
    ) -> MockChunkInfo:
        return MockChunkInfo(
            content=content,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            file_hash=file_hash,
            embedding=embedding or [0.1, 0.2, 0.3]
        )
    
    return _create_chunk_info


@pytest.fixture
def mock_chunkable_files_factory():
    """Factory for creating mock chunkable files dictionaries."""
    def _create_chunkable_files(
        file_count: int = 3,
        file_prefix: str = "test_file",
        file_extension: str = "py",
        hash_prefix: str = "hash"
    ) -> Dict[str, str]:
        return {
            f"src/{file_prefix}_{i}.{file_extension}": f"{hash_prefix}_{i}"
            for i in range(file_count)
        }
    
    return _create_chunkable_files


# Performance and stress test fixtures
@pytest.fixture
def large_chunk_info_list(mock_chunk_info_factory) -> List[MockChunkInfo]:
    """Create a large list of ChunkInfo objects for performance testing."""
    chunks = []
    for i in range(100):  # Create 100 chunks
        chunk = mock_chunk_info_factory(
            content=f"def function_{i}():\n    pass",
            file_path=f"src/file_{i}.py",
            file_hash=f"file_hash_{i}",
            embedding=[0.01 * i, 0.02 * i, 0.03 * i] if i % 2 == 0 else None
        )
        chunks.append(chunk)
    
    return chunks


@pytest.fixture
def large_chunkable_files(mock_chunkable_files_factory) -> Dict[str, str]:
    """Create a large dictionary of chunkable files for performance testing."""
    return mock_chunkable_files_factory(file_count=50)


# Additional fixtures for initialization manager tests
@pytest.fixture
def initialization_manager(mock_weaviate_clients, mock_process_executor, mock_one_dev_client):
    """Create a mock InitializationManager instance for testing"""
    manager = Mock()
    manager.weaviate_client = mock_weaviate_clients
    manager.process_executor = mock_process_executor
    manager.chunk_cleanup_task = None
    
    # Mock the process_chunks_cleanup method
    def mock_process_chunks_cleanup(chunks):
        exclusion_hashes = [chunk.content_hash for chunk in chunks]
        
        # Mock the cleanup manager creation and task
        mock_task = Mock()
        manager.chunk_cleanup_task = mock_task
        return mock_task
    
    manager.process_chunks_cleanup = mock_process_chunks_cleanup
    return manager


# Pytest markers for test categorization
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration  
pytest.mark.slow = pytest.mark.slow