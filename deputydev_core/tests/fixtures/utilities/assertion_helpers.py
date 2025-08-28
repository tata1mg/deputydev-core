"""
Assertion helper fixtures for DeputyDev Core test suite.

This module contains fixtures for assertion helper functions.
"""

from typing import List
import pytest

from ..data.mock_models import ChunkInfo


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