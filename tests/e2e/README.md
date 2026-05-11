# E2E Tests

These tests require a running server and (for flow tests) Supabase credentials.

## Quick run (no auth required)
```bash
pip install playwright pytest-playwright
playwright install chromium
uvicorn saas.api.main:app --port 8000 &
pytest tests/e2e/test_auth_flows.py -m e2e -k "not unauthenticated" -v
```

## Full flow tests (requires test Supabase account)
```bash
E2E_RUN=1 \
E2E_TEST_EMAIL=your-test@example.com \
E2E_BASE_URL=http://localhost:8000 \
pytest tests/e2e/ -m e2e -v
```
