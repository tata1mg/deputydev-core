"""
Sample data fixtures for DeputyDev Core test suite.

This module contains fixtures for sample data collections.
"""

from typing import Dict
import pytest


@pytest.fixture
def sample_chunkable_files() -> Dict[str, str]:
    """Sample dictionary of chunkable files and their hashes."""
    return {
        "src/main.py": "hash_main_py",
        "src/utils.py": "hash_utils_py", 
        "src/models/user.py": "hash_user_py",
        "tests/test_main.py": "hash_test_main_py",
        "docs/README.md": "hash_readme_md"
    }


@pytest.fixture
def empty_chunkable_files() -> Dict[str, str]:
    """Empty dictionary of chunkable files."""
    return {}