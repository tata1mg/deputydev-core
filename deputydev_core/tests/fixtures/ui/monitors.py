"""
Monitor fixtures for DeputyDev Core test suite.

This module contains fixtures for monitoring components.
"""

from unittest.mock import Mock
import pytest

try:
    from deputydev_core.utils.file_indexing_monitor import FileIndexingMonitor
except ImportError:
    FileIndexingMonitor = Mock


@pytest.fixture
def mock_file_indexing_monitor():
    """Create a mock FileIndexingMonitor."""
    return Mock(spec=FileIndexingMonitor)