"""
HTTP service client fixtures for DeputyDev Core test suite.

This module contains fixtures for HTTP service client mocks.
"""

from unittest.mock import Mock
import pytest

try:
    from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
except ImportError:
    OneDevClient = Mock


@pytest.fixture
def mock_one_dev_client():
    """Create a mock OneDevClient."""
    return Mock(spec=OneDevClient)