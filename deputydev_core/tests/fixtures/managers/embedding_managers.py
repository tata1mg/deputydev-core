"""
Embedding manager fixtures for DeputyDev Core test suite.

This module contains fixtures specifically for embedding managers.
"""

from unittest.mock import Mock
import pytest

try:
    from deputydev_core.services.embedding.extension_embedding_manager import (
        ExtensionEmbeddingManager,
    )
except ImportError:
    ExtensionEmbeddingManager = Mock

try:
    from deputydev_core.services.embedding.pr_review_embedding_manager import (
        PRReviewEmbeddingManager,
    )
except ImportError:
    PRReviewEmbeddingManager = Mock


@pytest.fixture
def mock_extension_embedding_manager():
    """Create a mock ExtensionEmbeddingManager."""
    return Mock(spec=ExtensionEmbeddingManager)


@pytest.fixture
def mock_pr_review_embedding_manager():
    """Create a mock PRReviewEmbeddingManager."""
    return Mock(spec=PRReviewEmbeddingManager)