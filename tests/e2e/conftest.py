"""E2E test configuration. Requires: pip install playwright pytest-playwright"""
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end (require running server)")

@pytest.fixture(scope="session")
def base_url():
    import os
    return os.environ.get("E2E_BASE_URL", "http://localhost:8000")

@pytest.fixture(scope="session")
def test_email():
    import os
    return os.environ.get("E2E_TEST_EMAIL", "e2e-test@aianalystweekly.com")

@pytest.fixture(scope="session")
def test_password():
    return "E2eTestPassword123!"
