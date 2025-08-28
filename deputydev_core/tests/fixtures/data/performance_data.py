"""
Performance test data fixtures for DeputyDev Core test suite.

This module contains fixtures for large datasets used in performance testing.
"""

from typing import Dict, List
import pytest

from .mock_models import MockChunkInfo


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