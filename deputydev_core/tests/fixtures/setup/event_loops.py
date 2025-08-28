"""
Event loop fixtures for DeputyDev Core test suite.

This module contains fixtures for asyncio event loop configuration.
"""

import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    """Create an event loop policy for the test session."""
    return asyncio.DefaultEventLoopPolicy()