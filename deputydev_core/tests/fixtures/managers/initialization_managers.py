"""
Initialization manager fixtures for DeputyDev Core test suite.

This module contains fixtures specifically for initialization managers.
"""

from unittest.mock import Mock
import pytest


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