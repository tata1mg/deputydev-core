"""
System client fixtures for DeputyDev Core test suite.

This module contains fixtures for system-level clients like ProcessExecutor.
"""

from concurrent.futures import ProcessPoolExecutor
from unittest.mock import Mock
import pytest


@pytest.fixture
def mock_process_executor():
    """Create a mock ProcessPoolExecutor."""
    return Mock(spec=ProcessPoolExecutor)