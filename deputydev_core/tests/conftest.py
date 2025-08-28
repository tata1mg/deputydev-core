"""
Pytest configuration and shared fixtures for DeputyDev Core test suite.

This is the main conftest.py file that imports fixtures from the organized
fixtures package and sets up pytest configuration.
"""

import pytest

# Import setup fixtures first (these need to run before other imports)
from deputydev_core.tests.fixtures.setup.event_loops import *

# Import client fixtures
from deputydev_core.tests.fixtures.clients.weaviate_clients import *
from deputydev_core.tests.fixtures.clients.http_service_clients import *
from deputydev_core.tests.fixtures.clients.system_clients import *

# Import repository fixtures
from deputydev_core.tests.fixtures.repositories.local_repositories import *

# Import UI fixtures
from deputydev_core.tests.fixtures.ui.progress_bars import *
from deputydev_core.tests.fixtures.ui.monitors import *

# Import data fixtures
from deputydev_core.tests.fixtures.data.mock_models import *
from deputydev_core.tests.fixtures.data.sample_data import *
from deputydev_core.tests.fixtures.data.chunk_data import *
from deputydev_core.tests.fixtures.data.performance_data import *

# Import utility fixtures
from deputydev_core.tests.fixtures.utilities.factories import *
from deputydev_core.tests.fixtures.utilities.assertion_helpers import *

# Import manager fixtures
from deputydev_core.tests.fixtures.managers.embedding_managers import *
from deputydev_core.tests.fixtures.managers.initialization_managers import *


# Pytest Configuration
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
