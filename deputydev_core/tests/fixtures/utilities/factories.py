"""
Factory fixtures for DeputyDev Core test suite.

This module contains factory fixtures for creating test objects with custom parameters.
"""

from typing import Dict, List
import pytest

from ..data.mock_models import MockChunkInfo


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