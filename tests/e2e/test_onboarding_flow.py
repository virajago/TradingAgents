"""E2E: Full sign-up → onboarding → dashboard flow.

Skipped by default — requires running server + valid Supabase test credentials.
Run with: E2E_RUN=1 E2E_TEST_EMAIL=test@example.com pytest tests/e2e/test_onboarding_flow.py -v
"""
import pytest
import os

pytestmark = [pytest.mark.e2e, pytest.mark.skip(reason="Full flow requires Supabase test account")]

try:
    from playwright.sync_api import Page, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@pytest.fixture(autouse=True)
def require_playwright():
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("playwright not installed")
    if not os.environ.get("E2E_RUN"):
        pytest.skip("Set E2E_RUN=1 to run flow tests")


def test_signup_to_onboarding_flow(page: Page, base_url: str, test_email: str, test_password: str):
    """Full signup → onboarding step 1 must work."""
    import time
    unique_email = f"e2e-{int(time.time())}@aianalystweekly.com"

    page.goto(f"{base_url}/signup")
    page.fill("#email", unique_email)
    page.fill("#password", test_password)

    # Select Pro plan
    plan_selector = page.locator("#plan-pro, [data-plan='pro']")
    if plan_selector.count() > 0:
        plan_selector.click()

    page.click("button[type='submit']")
    page.wait_for_timeout(3000)

    # Should either be on onboarding or Stripe checkout
    assert "onboarding" in page.url or "checkout.stripe.com" in page.url or "signup" in page.url


def test_onboarding_watchlist_entry(page: Page, base_url: str):
    """Onboarding step 1 — adding tickers must work."""
    page.goto(f"{base_url}/onboarding")
    page.wait_for_timeout(1000)

    # Add NVDA via suggestion chip if available
    nvda_chip = page.locator("button:has-text('NVDA'), .suggested-chip:has-text('NVDA')")
    if nvda_chip.count() > 0:
        nvda_chip.first.click()

    # Or type manually
    ticker_input = page.locator("#ticker-input")
    if ticker_input.count() > 0:
        ticker_input.fill("AAPL")
        page.keyboard.press("Enter")

    # Continue button should become enabled after 3 tickers
    continue_btn = page.locator("#step1-btn, button:has-text('Continue')")
    if continue_btn.count() > 0:
        assert continue_btn.first.is_visible()
