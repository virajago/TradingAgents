"""Shared fixtures for SaaS API tests.

This conftest stubs out all external heavy dependencies (fastapi, supabase,
stripe, tradingagents pipeline) at the sys.modules level so the test suite
runs without real API keys or a network connection.
"""
from __future__ import annotations

import os
import pathlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the project root is on sys.path so `saas.*` is importable when
# running pytest from any directory (e.g. `python -m pytest tests/saas/`).
_REPO_ROOT = str(pathlib.Path(__file__).parent.parent.parent.resolve())
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ---------------------------------------------------------------------------
# Stub the entire external dependency tree before any saas.* import happens.
# This must run at collection time, not inside a fixture, because Python
# caches module objects immediately on import.
# ---------------------------------------------------------------------------

def _make_mock_module(name: str, **attrs) -> types.ModuleType:
    """Return a MagicMock dressed as a module so attribute access works."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# ── fastapi stubs ──────────────────────────────────────────────────────────
# We only stub the parts that are imported at module-load time in saas/*.
# Runtime behaviour (routing, dependency injection, status codes) is handled
# by the real fastapi if it is installed, or by the mock otherwise.

if "fastapi" not in sys.modules:
    import importlib
    try:
        importlib.import_module("fastapi")
    except ModuleNotFoundError:
        # Build a minimal fake fastapi tree
        fastapi_mod = _make_mock_module("fastapi")

        class _HTTPException(Exception):
            def __init__(self, status_code: int = 400, detail: str = ""):
                self.status_code = status_code
                self.detail = detail

        class _status:
            HTTP_200_OK = 200
            HTTP_201_CREATED = 201
            HTTP_202_ACCEPTED = 202
            HTTP_204_NO_CONTENT = 204
            HTTP_400_BAD_REQUEST = 400
            HTTP_401_UNAUTHORIZED = 401
            HTTP_402_PAYMENT_REQUIRED = 402
            HTTP_403_FORBIDDEN = 403
            HTTP_404_NOT_FOUND = 404
            HTTP_409_CONFLICT = 409
            HTTP_422_UNPROCESSABLE_ENTITY = 422
            HTTP_429_TOO_MANY_REQUESTS = 429
            HTTP_500_INTERNAL_SERVER_ERROR = 500

        fastapi_mod.HTTPException = _HTTPException
        fastapi_mod.status = _status
        fastapi_mod.APIRouter = MagicMock
        fastapi_mod.Depends = lambda f: f
        fastapi_mod.FastAPI = MagicMock
        fastapi_mod.Request = MagicMock
        fastapi_mod.Header = MagicMock
        fastapi_mod.Query = MagicMock
        fastapi_mod.BackgroundTasks = MagicMock

        _make_mock_module("fastapi.middleware")
        _make_mock_module("fastapi.middleware.cors", CORSMiddleware=MagicMock)
        _make_mock_module("fastapi.security",
                          HTTPBearer=MagicMock,
                          HTTPAuthorizationCredentials=MagicMock)
        _make_mock_module("fastapi.staticfiles", StaticFiles=MagicMock)

# ── supabase stubs ─────────────────────────────────────────────────────────
if "supabase" not in sys.modules:
    try:
        import importlib
        importlib.import_module("supabase")
    except ModuleNotFoundError:
        _make_mock_module("supabase", Client=MagicMock, create_client=MagicMock)

# ── stripe stubs ───────────────────────────────────────────────────────────
if "stripe" not in sys.modules:
    try:
        import importlib
        importlib.import_module("stripe")
    except ModuleNotFoundError:
        stripe_mod = _make_mock_module("stripe")
        stripe_mod.Webhook = MagicMock
        stripe_mod.Customer = MagicMock
        stripe_mod.error = types.SimpleNamespace(
            SignatureVerificationError=Exception,
            StripeError=Exception,
        )
        _make_mock_module("stripe.error",
                          SignatureVerificationError=Exception,
                          StripeError=Exception)

# ── pydantic stubs ─────────────────────────────────────────────────────────
if "pydantic" not in sys.modules:
    try:
        import importlib
        importlib.import_module("pydantic")
    except ModuleNotFoundError:
        pydantic_mod = _make_mock_module("pydantic")

        class _BaseModel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

            @classmethod
            def model_validate(cls, data):
                return cls(**data)

            def model_dump(self):
                return vars(self)

        pydantic_mod.BaseModel = _BaseModel
        pydantic_mod.field_validator = lambda *a, **kw: (lambda f: f)
        _make_mock_module("pydantic_settings", BaseSettings=_BaseModel)

# ── yfinance stub ──────────────────────────────────────────────────────────
if "yfinance" not in sys.modules:
    try:
        import importlib
        importlib.import_module("yfinance")
    except ModuleNotFoundError:
        _make_mock_module("yfinance", Ticker=MagicMock)

# ── tradingagents pipeline stubs ───────────────────────────────────────────
for _mod_path in [
    "tradingagents",
    "tradingagents.pipeline",
    "tradingagents.pipeline.runner",
    "tradingagents.pipeline.checkpoint",
    "tradingagents.pipeline.state",
]:
    if _mod_path not in sys.modules:
        _make_mock_module(_mod_path)

# ── resend stub ────────────────────────────────────────────────────────────
if "resend" not in sys.modules:
    try:
        import importlib
        importlib.import_module("resend")
    except ModuleNotFoundError:
        _make_mock_module("resend")

# ── saas.workers.* stubs ──────────────────────────────────────────────────
# Stub every worker module so internal.py (which imports all of them at
# module load time) doesn't try to pull in tradingagents pipeline code.

if "saas.workers" not in sys.modules:
    _make_mock_module("saas.workers")

if "saas.workers.analysis_worker" not in sys.modules:
    _worker_mod = _make_mock_module("saas.workers.analysis_worker")
    _worker_mod.AGENT_NAMES = [
        "Market Analyst",
        "Sentiment Analyst",
        "News Analyst",
        "Fundamentals Analyst",
        "Research Manager",
        "Trader",
    ]

    def _get_task(task_id: str):  # noqa: ANN001
        return None

    async def _run_analysis(**kwargs):  # noqa: ANN001
        return {}

    def _fetch_portfolio_context(supabase, user_id: str):  # noqa: ANN001
        return {}

    _worker_mod.get_task = _get_task
    _worker_mod.run_analysis = _run_analysis
    _worker_mod.run_analysis_task = AsyncMock(return_value={"final_state": {}, "signal": "HOLD"})
    _worker_mod._fetch_portfolio_context = _fetch_portfolio_context

if "saas.workers.batch_scheduler" not in sys.modules:
    _batch = _make_mock_module("saas.workers.batch_scheduler")
    _batch.run_weekly_batch = AsyncMock()

if "saas.workers.alert_monitor" not in sys.modules:
    _alert = _make_mock_module("saas.workers.alert_monitor")
    _alert.check_alerts = AsyncMock()

if "saas.workers.verdict_settler" not in sys.modules:
    _settler = _make_mock_module("saas.workers.verdict_settler")
    _settler.settle_verdicts = AsyncMock()

# ── saas.email.* stubs ────────────────────────────────────────────────────
# Stub the entire saas.email subpackage so importing any sub-module (lifecycle,
# sender, formatter) does not try to import resend or other missing packages.
if "saas.email" not in sys.modules:
    _make_mock_module("saas.email")
if "saas.email.lifecycle" not in sys.modules:
    _lifecycle = _make_mock_module("saas.email.lifecycle")
    _lifecycle.track_event = AsyncMock()
if "saas.email.sender" not in sys.modules:
    _sender = _make_mock_module("saas.email.sender")
    _sender.send_alert_email = AsyncMock()
    _sender.send_digest_email = AsyncMock()
    _sender.send_welcome_email = AsyncMock()
if "saas.email.formatter" not in sys.modules:
    _make_mock_module("saas.email.formatter")


# ---------------------------------------------------------------------------
# Fake users and supabase helpers
# ---------------------------------------------------------------------------

FAKE_USER = {"id": "user-test-uuid-1234", "email": "test@example.com"}
FAKE_USER_2 = {"id": "user-test-uuid-5678", "email": "other@example.com"}


async def fake_get_current_user():
    """Dependency override: always return the test user."""
    return FAKE_USER


async def fake_verify_internal_secret():
    """Dependency override: always pass the internal secret check."""
    return None


def fake_get_supabase():
    """Returns a mock Supabase client with sensible defaults."""
    mock = MagicMock()
    # Chainable query builder — default returns empty data
    chain = mock.table.return_value
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.range.return_value = chain
    chain.limit.return_value = chain
    chain.single.return_value = chain
    chain.execute.return_value.data = []
    chain.insert.return_value.execute.return_value.data = [{}]
    chain.update.return_value.eq.return_value.execute.return_value.data = [{}]
    chain.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    chain.upsert.return_value.execute.return_value.data = [{}]
    mock.rpc.return_value.execute.return_value.data = 100
    return mock


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _set_env_vars(tmp_path_factory):
    """Set env vars required by saas.config.settings so Settings() doesn't raise."""
    import os
    defaults = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_ANON_KEY": "test-anon-key",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
        "SUPABASE_JWT_SECRET": "test-jwt-secret",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        "STRIPE_SECRET_KEY": "sk_test_placeholder",
        "STRIPE_WEBHOOK_SECRET": "whsec_test_placeholder",
        "INTERNAL_API_SECRET": "test-internal-secret",
        "RESEND_API_KEY": "test-resend-key",
    }
    for k, v in defaults.items():
        os.environ.setdefault(k, v)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _fastapi_is_real() -> bool:
    """Return True if the real fastapi package is installed (not our stub)."""
    mod = sys.modules.get("fastapi")
    if mod is None:
        return False
    # Our stub is a plain types.ModuleType with no __version__; real fastapi has it.
    return hasattr(mod, "__version__")


@pytest.fixture
async def client():
    """AsyncClient with auth + supabase mocked out.

    Uses the real FastAPI app. Skips cleanly when fastapi/httpx are not
    installed in the current environment.
    """
    if not _fastapi_is_real():
        pytest.skip("fastapi not installed — install saas/requirements.txt to run route tests")

    try:
        from httpx import AsyncClient, ASGITransport
        from saas.api.main import app
        from saas.api.deps import get_current_user, get_supabase, verify_internal_secret

        app.dependency_overrides[get_current_user] = fake_get_current_user
        app.dependency_overrides[verify_internal_secret] = fake_verify_internal_secret
        app.dependency_overrides[get_supabase] = fake_get_supabase

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

        app.dependency_overrides.clear()
    except (ModuleNotFoundError, ImportError) as exc:
        pytest.skip(f"FastAPI/httpx not installed — skipping route test: {exc}")


@pytest.fixture
async def unauthed_client():
    """AsyncClient with NO auth override.

    Used to verify that unauthenticated requests are rejected. Skips
    cleanly when fastapi/httpx are not installed.
    """
    if not _fastapi_is_real():
        pytest.skip("fastapi not installed — install saas/requirements.txt to run route tests")

    try:
        from httpx import AsyncClient, ASGITransport
        from saas.api.main import app
        from saas.api.deps import get_supabase

        # Still mock supabase so we don't hit the real DB, but do NOT override auth.
        app.dependency_overrides[get_supabase] = fake_get_supabase

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

        app.dependency_overrides.clear()
    except (ModuleNotFoundError, ImportError) as exc:
        pytest.skip(f"FastAPI/httpx not installed — skipping route test: {exc}")
