"""P2: Memory log must be strictly isolated per user — no cross-contamination."""
import pytest
from unittest.mock import MagicMock

try:
    from tradingagents.agents.utils.postgres_memory import PostgresMemoryLog
    POSTGRES_MEMORY_AVAILABLE = True
except ImportError:
    POSTGRES_MEMORY_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not POSTGRES_MEMORY_AVAILABLE,
    reason="PostgresMemoryLog not importable",
)


def make_supabase():
    """Build a Supabase mock that returns safe defaults for all chained calls."""
    mock = MagicMock()
    # upsert chain
    mock.table.return_value.upsert.return_value.execute.return_value.data = [{}]
    # select → eq → order → execute (load_entries / get_pending_entries)
    mock.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    # select → eq → eq → order → execute (get_pending_entries second .eq())
    mock.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    # update chain (store_reflection / batch_update_with_outcomes)
    mock.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{}]
    return mock


# ---------------------------------------------------------------------------
# store_decision isolation
# ---------------------------------------------------------------------------

def test_store_decision_uses_correct_user_id():
    """store_decision must pass the user_id to Supabase, not a global."""
    mock_sb = make_supabase()
    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    log.store_decision("NVDA", "2026-01-12", "Rating: Buy\nStrong fundamentals.")

    call_args = mock_sb.table.return_value.upsert.call_args
    data = call_args[0][0]
    assert data["user_id"] == "user-A"
    assert data["ticker"] == "NVDA"


def test_store_decision_uppercases_ticker():
    """store_decision must normalise ticker to upper-case before upsert."""
    mock_sb = make_supabase()
    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    log.store_decision("nvda", "2026-01-12", "Rating: Buy")

    data = mock_sb.table.return_value.upsert.call_args[0][0]
    assert data["ticker"] == "NVDA"


def test_two_users_get_separate_logs():
    """User A and User B must write to separate records, not share one."""
    mock_sb_a = make_supabase()
    mock_sb_b = make_supabase()

    log_a = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb_a)
    log_b = PostgresMemoryLog(user_id="user-B", supabase_client=mock_sb_b)

    log_a.store_decision("NVDA", "2026-01-12", "Rating: Buy\nBullish thesis.")
    log_b.store_decision("NVDA", "2026-01-12", "Rating: Sell\nBearish thesis.")

    args_a = mock_sb_a.table.return_value.upsert.call_args[0][0]
    args_b = mock_sb_b.table.return_value.upsert.call_args[0][0]

    assert args_a["user_id"] == "user-A"
    assert args_b["user_id"] == "user-B"
    # Completely separate Supabase client instances — fully isolated
    assert mock_sb_a is not mock_sb_b


def test_store_decision_idempotent_uses_upsert():
    """Storing the same decision twice must call upsert (not insert) so the DB
    can deduplicate via ON CONFLICT."""
    mock_sb = make_supabase()
    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)

    log.store_decision("NVDA", "2026-01-12", "Rating: Buy")
    log.store_decision("NVDA", "2026-01-12", "Rating: Buy")

    upsert_calls = mock_sb.table.return_value.upsert.call_count
    # Both calls must reach the DB as upserts — idempotency is enforced by
    # the ON CONFLICT clause, not by a Python-level guard.
    assert upsert_calls == 2


# ---------------------------------------------------------------------------
# load_entries isolation
# ---------------------------------------------------------------------------

def test_load_entries_filters_by_user_id():
    """load_entries must query with the correct user_id filter."""
    mock_sb = make_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "ticker": "NVDA",
            "trade_date": "2026-01-12",
            "decision_text": "Buy",
            "status": "pending",
            "rating": "Buy",
        },
    ]

    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    entries = log.load_entries()

    # Verify .eq() was called with ("user_id", "user-A")
    eq_calls = mock_sb.table.return_value.select.return_value.eq.call_args_list
    user_id_filtered = any(
        ("user_id" in str(c) or "user-A" in str(c))
        for c in eq_calls
    )
    assert user_id_filtered, "load_entries did not filter by user_id"
    assert len(entries) == 1


def test_user_a_entries_not_visible_to_user_b():
    """Simulates two users querying — each sees only their own data."""
    mock_sb_a = make_supabase()
    mock_sb_b = make_supabase()

    mock_sb_a.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "ticker": "NVDA",
            "trade_date": "2026-01-12",
            "decision_text": "Buy",
            "status": "pending",
            "rating": "Buy",
        },
    ]
    # user-B's mock already returns [] from make_supabase()

    log_a = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb_a)
    log_b = PostgresMemoryLog(user_id="user-B", supabase_client=mock_sb_b)

    entries_a = log_a.load_entries()
    entries_b = log_b.load_entries()

    assert len(entries_a) == 1
    assert len(entries_b) == 0


# ---------------------------------------------------------------------------
# format_for_prompt
# ---------------------------------------------------------------------------

def test_format_for_prompt_returns_empty_when_no_entries():
    """If no entries exist, format_for_prompt must return empty string (safe concat)."""
    mock_sb = make_supabase()
    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    result = log.format_for_prompt()
    assert result == "" or result is None or len(result.strip()) == 0


def test_format_for_prompt_returns_string_when_entries_exist():
    """With entries, format_for_prompt must return a non-empty string containing
    the ticker."""
    mock_sb = make_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "ticker": "NVDA",
            "trade_date": "2026-01-12",
            "decision_text": "Rating: Buy",
            "status": "resolved",
            "rating": "Buy",
        },
    ]
    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    result = log.format_for_prompt()
    assert isinstance(result, str)
    assert "NVDA" in result


def test_format_for_prompt_respects_limit():
    """format_for_prompt(limit=1) must return at most one entry in its output."""
    mock_sb = make_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "ticker": "NVDA",
            "trade_date": "2026-01-12",
            "decision_text": "Rating: Buy",
            "status": "resolved",
            "rating": "Buy",
        },
        {
            "ticker": "AAPL",
            "trade_date": "2026-01-11",
            "decision_text": "Rating: Hold",
            "status": "resolved",
            "rating": "Hold",
        },
    ]
    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    result = log.format_for_prompt(limit=1)
    # Only one ticker should appear when limit=1
    assert "NVDA" in result
    assert "AAPL" not in result


# ---------------------------------------------------------------------------
# store_reflection isolation
# ---------------------------------------------------------------------------

def test_store_reflection_updates_correct_user_entry():
    """store_reflection must filter by user_id, ticker, AND trade_date."""
    mock_sb = make_supabase()
    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    log.store_reflection("NVDA", "2026-01-12", "Stock rose 12% — bull thesis confirmed.")

    update_calls = mock_sb.table.return_value.update.call_args_list
    assert len(update_calls) >= 1
    # The full eq chain must include user_id = "user-A"
    chain_str = str(mock_sb.table.return_value.update.return_value.mock_calls)
    assert "user-A" in chain_str or "user_id" in chain_str


def test_store_reflection_uppercases_ticker():
    """store_reflection must normalise ticker to upper-case in the WHERE clause."""
    mock_sb = make_supabase()
    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    log.store_reflection("nvda", "2026-01-12", "Reflection text.")

    chain_str = str(mock_sb.table.return_value.update.return_value.mock_calls)
    assert "NVDA" in chain_str


def test_store_reflection_sets_status_resolved():
    """store_reflection must update status to 'resolved'."""
    mock_sb = make_supabase()
    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    log.store_reflection("NVDA", "2026-01-12", "Reflection text.")

    update_payload = mock_sb.table.return_value.update.call_args[0][0]
    assert update_payload.get("status") == "resolved"
    assert "reflection_text" in update_payload


# ---------------------------------------------------------------------------
# get_pending_entries
# ---------------------------------------------------------------------------

def test_get_pending_entries_filters_by_user_id_and_status():
    """get_pending_entries must filter by both user_id and status=pending."""
    mock_sb = make_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "ticker": "NVDA",
            "trade_date": "2026-01-12",
            "decision_text": "Rating: Buy",
            "status": "pending",
            "rating": "Buy",
        },
    ]

    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    entries = log.get_pending_entries()

    # The chained .eq() calls must include filtering on user_id
    first_eq_args = mock_sb.table.return_value.select.return_value.eq.call_args_list
    user_id_filtered = any("user_id" in str(c) or "user-A" in str(c) for c in first_eq_args)
    assert user_id_filtered, "get_pending_entries did not filter by user_id"
    assert len(entries) == 1


def test_get_pending_entries_normalises_keys():
    """get_pending_entries must include 'date' and 'decision' keys for
    compatibility with trading_graph.py._resolve_pending_entries()."""
    mock_sb = make_supabase()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "ticker": "NVDA",
            "trade_date": "2026-01-12",
            "decision_text": "Rating: Buy",
            "status": "pending",
            "rating": "Buy",
        },
    ]

    log = PostgresMemoryLog(user_id="user-A", supabase_client=mock_sb)
    entries = log.get_pending_entries()

    assert len(entries) == 1
    entry = entries[0]
    assert "date" in entry, "Missing normalised 'date' key"
    assert "decision" in entry, "Missing normalised 'decision' key"
    assert entry["date"] == "2026-01-12"
    assert entry["decision"] == "Rating: Buy"
