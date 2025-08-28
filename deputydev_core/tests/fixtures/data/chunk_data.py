"""
Chunk data fixtures for DeputyDev Core test suite.

This module contains fixtures for chunk-related data objects.
"""

from typing import Dict, List
import pytest

from .mock_models import MockChunkInfo


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
def empty_chunk_info_list() -> List[MockChunkInfo]:
    """Empty list of ChunkInfo objects."""
    return []


@pytest.fixture
def sample_existing_file_wise_chunks(sample_chunk_info_list) -> Dict[str, List[MockChunkInfo]]:
    """Sample existing file-wise chunks for testing."""
    file_wise_chunks = {}
    
    for chunk in sample_chunk_info_list[:3]:  # Use first 3 chunks
        if chunk.file_path not in file_wise_chunks:
            file_wise_chunks[chunk.file_path] = []
        file_wise_chunks[chunk.file_path].append(chunk)
    
    return file_wise_chunks