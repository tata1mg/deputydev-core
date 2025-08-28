"""
Local repository fixtures for DeputyDev Core test suite.

This module contains fixtures for local repository service mocks.
"""

from unittest.mock import Mock
import pytest

try:
    from deputydev_core.services.repo.local_repo.base_local_repo_service import (
        BaseLocalRepo,
    )
except ImportError:
    BaseLocalRepo = Mock


@pytest.fixture
def mock_local_repo():
    """Create a mock BaseLocalRepo."""
    repo = Mock(spec=BaseLocalRepo)
    repo.repo_path = "/test/repo/path"
    repo.get_chunkable_files_and_commit_hashes = Mock(return_value={})
    return repo