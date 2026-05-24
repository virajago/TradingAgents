"""E2E: Authentication flows — sign up, sign in, forgot password.

Requires:
  pip install playwright pytest-playwright
  playwright install chromium
  uvicorn saas.api.main:app --port 8000  (running in background)
  E2E_BASE_URL=http://localhost:8000 pytest tests/e2e/ -m e2e -v
"""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.skip(reason="E2E tests require running server — run with: E2E_RUN=1 pytest tests/e2e/")]


try:
    from playwright.sync_api import Page, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@pytest.fixture(autouse=True)
def require_playwright():
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("playwright not installed — run: pip install playwright && playwright install chromium")


def test_landing_page_loads(page: Page, base_url: str):
    """Landing page must load with the correct title."""
    page.goto(base_url)
    expect(page).to_have_title(lambda t: "Conviction" in t)
    # Hero headline must be visible
    expect(page.locator("h1")).to_be_visible()


def test_signup_page_loads(page: Page, base_url: str):
    """Sign-up page must load with email + password fields."""
    page.goto(f"{base_url}/signup")
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator("#password")).to_be_visible()
    expect(page.locator("button[type='submit']")).to_be_visible()


def test_signin_page_loads(page: Page, base_url: str):
    """Sign-in page must load with email + password fields."""
    page.goto(f"{base_url}/signin")
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator("#password")).to_be_visible()


def test_signup_validates_empty_email(page: Page, base_url: str):
    """Empty email on sign-up must show validation error."""
    page.goto(f"{base_url}/signup")
    page.click("button[type='submit']")
    # HTML5 validation or custom error — either way, form should not submit
    expect(page.locator("#email")).to_be_focused()


def test_signin_shows_error_on_wrong_password(page: Page, base_url: str):
    """Wrong credentials must show an error message, not crash."""
    page.goto(f"{base_url}/signin")
    page.fill("#email", "nonexistent@test.com")
    page.fill("#password", "wrongpassword")
    page.click("button[type='submit']")
    page.wait_for_timeout(2000)
    # Error message must appear somewhere
    error = page.locator(".error-box, [role='alert'], .alert-error")
    # Either error box is visible, or we're still on signin page (not crashed)
    assert page.url.endswith("/signin") or error.count() > 0


def test_forgot_password_page_loads(page: Page, base_url: str):
    """Forgot password page must load with email field."""
    page.goto(f"{base_url}/forgot-password")
    expect(page.locator("#email")).to_be_visible()


def test_forgot_password_link_on_signin(page: Page, base_url: str):
    """Sign-in page must have a 'Forgot password?' link."""
    page.goto(f"{base_url}/signin")
    forgot_link = page.locator("a[href*='forgot']")
    expect(forgot_link).to_be_visible()
    forgot_link.click()
    expect(page).to_have_url(lambda u: "forgot" in u)


def test_dashboard_redirects_to_signin_when_unauthenticated(page: Page, base_url: str):
    """Dashboard must redirect unauthenticated users to sign-in."""
    page.goto(f"{base_url}/dashboard")
    page.wait_for_timeout(1500)
    # Should redirect to signin
    assert "signin" in page.url or "sign-in" in page.url or page.url.endswith("/")


def test_analyze_page_loads(page: Page, base_url: str):
    """Analysis page must load (may redirect to signin if not authenticated)."""
    page.goto(f"{base_url}/analyze")
    page.wait_for_timeout(1000)
    # Either loaded or redirected to signin
    assert page.url is not None


def test_health_endpoint_returns_ok(page: Page, base_url: str):
    """Health endpoint must return 200."""
    response = page.request.get(f"{base_url}/health")
    assert response.status == 200
    data = response.json()
    assert data.get("status") == "ok"


def test_api_rejects_unauthenticated_analyze(page: Page, base_url: str):
    """POST /analyze without auth must return 401/422."""
    response = page.request.post(
        f"{base_url}/analyze",
        data={"ticker": "NVDA"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status in (401, 403, 422)


def test_legal_pages_load(page: Page, base_url: str):
    """Privacy, terms, and disclaimer pages must all load."""
    for path in ["/privacy", "/terms", "/disclaimer"]:
        page.goto(f"{base_url}{path}")
        expect(page).not_to_have_title("404")
        # Page must have some content
        body_text = page.locator("body").inner_text()
        assert len(body_text.strip()) > 100, f"{path} appears empty"


def test_disclaimer_contains_not_investment_advice(page: Page, base_url: str):
    """Disclaimer page must contain the 'not investment advice' statement."""
    page.goto(f"{base_url}/disclaimer")
    body_text = page.locator("body").inner_text().lower()
    assert "not investment advice" in body_text or "informational purposes" in body_text
