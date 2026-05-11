"""Integration: Supabase RLS — users can only see their own data.

Requires: supabase start + schema applied + INTEGRATION_RUN=1
"""
import pytest

pytestmark = pytest.mark.integration


def get_user_client(supabase_url, anon_key, email, password):
    """Sign in as a user and return their client (with JWT)."""
    from supabase import create_client
    client = create_client(supabase_url, anon_key)
    client.auth.sign_in_with_password({"email": email, "password": password})
    return client


class TestWatchlistRLS:
    def test_user_a_cannot_see_user_b_watchlist(self, admin_client, supabase_url, anon_key, user_a_id, user_b_id):
        """User A must not be able to read User B's watchlist items."""
        # Insert a watchlist item for user B using service role
        admin_client.table("watchlist_items").insert({
            "user_id": user_b_id,
            "ticker": "NVDA",
        }).execute()

        # Sign in as user A
        client_a = get_user_client(supabase_url, anon_key,
                                    "rls-test-user-a@aianalystweekly.com", "TestPassword123!")

        # User A reads watchlist — must not see user B's items
        result = client_a.table("watchlist_items").select("*").execute()
        tickers = [row["ticker"] for row in (result.data or [])]
        assert "NVDA" not in tickers or all(
            row["user_id"] == user_a_id for row in (result.data or [])
        ), "User A can see User B's watchlist items — RLS policy broken"

    def test_user_can_insert_own_watchlist(self, admin_client, supabase_url, anon_key, user_a_id):
        """User A can insert their own watchlist items."""
        client_a = get_user_client(supabase_url, anon_key,
                                    "rls-test-user-a@aianalystweekly.com", "TestPassword123!")
        result = client_a.table("watchlist_items").insert({
            "user_id": user_a_id,
            "ticker": "MSFT",
        }).execute()
        assert result.data is not None


class TestPortfolioRLS:
    def test_user_a_cannot_see_user_b_portfolio(self, admin_client, supabase_url, anon_key, user_a_id, user_b_id):
        """User A must not see User B's portfolio holdings."""
        admin_client.table("portfolio_holdings").insert({
            "user_id": user_b_id,
            "ticker": "AAPL",
            "shares": 100,
            "avg_cost_usd": 185.0,
        }).execute()

        client_a = get_user_client(supabase_url, anon_key,
                                    "rls-test-user-a@aianalystweekly.com", "TestPassword123!")
        result = client_a.table("portfolio_holdings").select("*").execute()
        for row in (result.data or []):
            assert row["user_id"] == user_a_id, "User A can see User B's portfolio — RLS broken"


class TestAnalysesRLS:
    def test_user_a_cannot_see_user_b_analyses(self, admin_client, supabase_url, anon_key, user_a_id, user_b_id):
        """User A must not see User B's analyses."""
        admin_client.table("analyses").insert({
            "user_id": user_b_id,
            "ticker": "GOOGL",
            "trade_date": "2026-01-12",
            "source": "on_demand",
            "status": "complete",
            "verdict": "BULLISH",
        }).execute()

        client_a = get_user_client(supabase_url, anon_key,
                                    "rls-test-user-a@aianalystweekly.com", "TestPassword123!")
        result = client_a.table("analyses").select("*").execute()
        for row in (result.data or []):
            assert row["user_id"] == user_a_id, "User A sees User B's analyses — RLS broken"


class TestServiceRoleBypassesRLS:
    def test_service_role_can_read_all_users(self, admin_client, user_a_id, user_b_id):
        """Service role (used by batch worker) must see all users' data."""
        # Insert watchlist for both users
        admin_client.table("watchlist_items").insert([
            {"user_id": user_a_id, "ticker": "META"},
            {"user_id": user_b_id, "ticker": "TSLA"},
        ]).execute()

        # Service role reads all
        result = admin_client.table("watchlist_items").select("*").execute()
        user_ids = {row["user_id"] for row in (result.data or [])}

        assert user_a_id in user_ids, "Service role cannot see User A's data"
        assert user_b_id in user_ids, "Service role cannot see User B's data"


class TestJournalRLS:
    def test_user_a_cannot_see_user_b_journal(self, admin_client, supabase_url, anon_key, user_a_id, user_b_id):
        """User A must not see User B's decision journal."""
        admin_client.table("journal_entries").insert({
            "user_id": user_b_id,
            "ticker": "NVDA",
            "action": "buy",
            "entry_date": "2026-01-12",
        }).execute()

        client_a = get_user_client(supabase_url, anon_key,
                                    "rls-test-user-a@aianalystweekly.com", "TestPassword123!")
        result = client_a.table("journal_entries").select("*").execute()
        for row in (result.data or []):
            assert row["user_id"] == user_a_id, "User A sees User B's journal — RLS broken"
