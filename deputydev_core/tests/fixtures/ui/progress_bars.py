"""
Progress bar fixtures for DeputyDev Core test suite.

This module contains fixtures for progress bar mocks.
"""

from unittest.mock import Mock
import pytest

try:
    from deputydev_core.utils.custom_progress_bar import CustomProgressBar
except ImportError:
    CustomProgressBar = Mock


@pytest.fixture
def mock_indexing_progress_bar():
    """Create a mock CustomProgressBar for indexing."""
    return Mock(spec=CustomProgressBar)


@pytest.fixture
def mock_embedding_progress_bar():
    """Create a mock CustomProgressBar for embedding."""
    return Mock(spec=CustomProgressBar)