"""Integration tests requiring a real local Supabase instance.

Start with: supabase start
Apply schema: supabase db push saas/db/schema.sql

Run: INTEGRATION_RUN=1 pytest tests/integration/ -v
"""
import os
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires local Supabase (supabase start)")

@pytest.fixture(scope="session", autouse=True)
def require_integration():
    if not os.environ.get("INTEGRATION_RUN"):
        pytest.skip("Set INTEGRATION_RUN=1 to run integration tests")

@pytest.fixture(scope="session")
def supabase_url():
    return os.environ.get("SUPABASE_URL", "http://localhost:54321")

@pytest.fixture(scope="session")
def service_role_key():
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

@pytest.fixture(scope="session")
def anon_key():
    return os.environ.get("SUPABASE_ANON_KEY", "")

@pytest.fixture(scope="session")
def admin_client(supabase_url, service_role_key):
    """Service-role client — bypasses RLS."""
    try:
        from supabase import create_client
        return create_client(supabase_url, service_role_key)
    except Exception:
        pytest.skip("Could not connect to Supabase")

@pytest.fixture
def user_a_id(admin_client):
    """Create a test user A and return their ID. Cleanup after test."""
    result = admin_client.auth.admin.create_user({
        "email": "rls-test-user-a@aianalystweekly.com",
        "password": "TestPassword123!",
        "email_confirm": True,
    })
    user_id = result.user.id
    yield user_id
    # Cleanup
    try:
        admin_client.auth.admin.delete_user(user_id)
    except Exception:
        pass

@pytest.fixture
def user_b_id(admin_client):
    result = admin_client.auth.admin.create_user({
        "email": "rls-test-user-b@aianalystweekly.com",
        "password": "TestPassword123!",
        "email_confirm": True,
    })
    user_id = result.user.id
    yield user_id
    try:
        admin_client.auth.admin.delete_user(user_id)
    except Exception:
        pass
