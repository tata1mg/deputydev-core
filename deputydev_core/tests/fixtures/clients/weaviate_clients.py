"""
Weaviate client fixtures for DeputyDev Core test suite.

This module contains fixtures specifically for Weaviate client mocks.
"""

from unittest.mock import Mock
import pytest

try:
    from weaviate import WeaviateAsyncClient, WeaviateClient
except ImportError:
    WeaviateAsyncClient = Mock
    WeaviateClient = Mock


class MockWeaviateSyncAndAsyncClients:
    def __init__(self, sync_client=None, async_client=None):
        self.sync_client = sync_client or Mock()
        self.async_client = async_client or Mock()


# Use our mock classes consistently
WeaviateSyncAndAsyncClients = MockWeaviateSyncAndAsyncClients


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