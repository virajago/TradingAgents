"""Tests for LocalCheckpoint, SupabaseCheckpoint, and get_checkpoint factory."""
import pytest
from dataclasses import asdict
from unittest.mock import MagicMock

from tradingagents.pipeline.state import AnalysisState
from tradingagents.pipeline.checkpoint import (
    LocalCheckpoint,
    SupabaseCheckpoint,
    get_checkpoint,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _sample_state(**overrides) -> AnalysisState:
    defaults = dict(ticker="NVDA", trade_date="2026-01-15")
    defaults.update(overrides)
    return AnalysisState(**defaults)


# ── LocalCheckpoint ────────────────────────────────────────────────────────

class TestLocalCheckpoint:
    def test_load_returns_none_when_no_file(self, tmp_path):
        cp = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15")
        assert cp.load() is None

    def test_save_creates_file(self, tmp_path):
        state = _sample_state()
        cp = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15")
        cp.save(state)
        assert cp._path.exists()

    def test_save_and_load_roundtrip(self, tmp_path):
        state = _sample_state(
            fundamentals_report="strong fundamentals",
            final_decision="BULLISH",
        )
        cp = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15")
        cp.save(state)
        loaded = cp.load()
        assert loaded is not None
        assert loaded.ticker == "NVDA"
        assert loaded.fundamentals_report == "strong fundamentals"
        assert loaded.final_decision == "BULLISH"

    def test_load_preserves_completed_agents(self, tmp_path):
        state = _sample_state()
        state.completed_agents = ["Fundamental Analyst", "Market Analyst"]
        state.agent_summaries = {"Fundamental Analyst": "done"}
        cp = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15")
        cp.save(state)
        loaded = cp.load()
        assert loaded.completed_agents == ["Fundamental Analyst", "Market Analyst"]
        assert loaded.agent_summaries["Fundamental Analyst"] == "done"

    def test_clear_removes_file(self, tmp_path):
        state = _sample_state()
        cp = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15")
        cp.save(state)
        cp.clear()
        assert cp.load() is None

    def test_clear_on_missing_file_does_not_raise(self, tmp_path):
        cp = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15")
        cp.clear()  # must not raise even if file doesn't exist

    def test_corrupt_file_returns_none(self, tmp_path):
        """A corrupt checkpoint file must not raise — returns None gracefully."""
        cp = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15")
        cp._path.write_text("not valid json {{{{{", encoding="utf-8")
        result = cp.load()
        assert result is None

    def test_user_id_scoping_separate_files(self, tmp_path):
        """Different user_ids must produce separate checkpoint files."""
        state_a = _sample_state(fundamentals_report="user_a_data")
        state_b = _sample_state(fundamentals_report="user_b_data")

        cp_a = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15", user_id="user_a")
        cp_b = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15", user_id="user_b")

        cp_a.save(state_a)
        cp_b.save(state_b)

        loaded_a = cp_a.load()
        loaded_b = cp_b.load()

        assert loaded_a.fundamentals_report == "user_a_data"
        assert loaded_b.fundamentals_report == "user_b_data"

    def test_user_id_scoping_no_cross_read(self, tmp_path):
        """user_a's checkpoint must not be visible to user_b."""
        state_a = _sample_state(market_report="secret")
        cp_a = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15", user_id="user_a")
        cp_b = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15", user_id="user_b")

        cp_a.save(state_a)
        # user_b has no checkpoint saved
        assert cp_b.load() is None

    def test_different_tickers_separate_files(self, tmp_path):
        """Different tickers must produce separate checkpoint files."""
        state_nvda = _sample_state(ticker="NVDA", market_report="nvda data")
        state_aapl = _sample_state(ticker="AAPL", market_report="aapl data")

        cp_nvda = LocalCheckpoint(str(tmp_path), "NVDA", "2026-01-15")
        cp_aapl = LocalCheckpoint(str(tmp_path), "AAPL", "2026-01-15")

        cp_nvda.save(state_nvda)
        cp_aapl.save(state_aapl)

        assert cp_nvda.load().market_report == "nvda data"
        assert cp_aapl.load().market_report == "aapl data"

    def test_checkpoint_directory_created_automatically(self, tmp_path):
        """The checkpoints subdirectory is created if it doesn't exist."""
        nested = tmp_path / "deep" / "nested" / "cache"
        cp = LocalCheckpoint(str(nested), "NVDA", "2026-01-15")
        cp.save(_sample_state())
        assert cp._path.exists()

    def test_ticker_with_slash_sanitized(self, tmp_path):
        """Tickers like 'BRK/B' must be sanitized for use in file names."""
        state = _sample_state(ticker="BRK/B", trade_date="2026-01-15")
        cp = LocalCheckpoint(str(tmp_path), "BRK/B", "2026-01-15")
        cp.save(state)
        loaded = cp.load()
        assert loaded is not None


# ── SupabaseCheckpoint ─────────────────────────────────────────────────────

class TestSupabaseCheckpoint:
    def _mock_supabase(self):
        """Return a minimal Supabase client mock."""
        mock_sb = MagicMock()
        # Default: upsert succeeds
        mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [{}]
        # Default: load finds nothing
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = None
        return mock_sb

    def test_save_calls_upsert_on_correct_table(self):
        mock_sb = self._mock_supabase()
        state = _sample_state()
        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        cp.save(state)
        mock_sb.table.assert_called_with("analysis_checkpoints")

    def test_save_includes_required_fields(self):
        mock_sb = self._mock_supabase()
        state = _sample_state()
        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        cp.save(state)

        upsert_call = mock_sb.table.return_value.upsert.call_args
        data = upsert_call[0][0]
        assert data["task_id"] == "task-abc"
        assert data["user_id"] == "user-123"
        assert data["ticker"] == "NVDA"
        assert "state" in data

    def test_save_stores_serializable_state(self):
        mock_sb = self._mock_supabase()
        state = _sample_state(fundamentals_report="cached", final_decision="BUY")
        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        cp.save(state)

        upsert_call = mock_sb.table.return_value.upsert.call_args
        stored_state = upsert_call[0][0]["state"]
        # State must be stored as a dict (serializable to jsonb)
        assert isinstance(stored_state, dict)
        assert stored_state["fundamentals_report"] == "cached"
        assert stored_state["final_decision"] == "BUY"

    def test_save_non_fatal_on_supabase_error(self):
        """save() must not raise if Supabase fails."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.side_effect = Exception("network error")

        state = _sample_state()
        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        cp.save(state)  # must not raise

    def test_load_returns_state_when_data_exists(self):
        """load() returns an AnalysisState when Supabase returns a matching row."""
        state = _sample_state(fundamentals_report="cached data")
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "state": asdict(state)
        }
        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        loaded = cp.load()

        assert loaded is not None
        assert loaded.fundamentals_report == "cached data"
        assert loaded.ticker == "NVDA"

    def test_load_returns_none_when_no_row(self):
        """load() returns None when Supabase finds no matching row."""
        mock_sb = self._mock_supabase()  # default: data=None
        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        assert cp.load() is None

    def test_load_returns_none_on_supabase_error(self):
        """load() must not raise on Supabase error — returns None."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.side_effect = Exception("DB error")

        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        assert cp.load() is None

    def test_load_queries_by_task_and_user(self):
        """load() must filter by both task_id and user_id."""
        mock_sb = self._mock_supabase()
        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        cp.load()

        # Verify .eq() was called with task_id and user_id filters
        select_chain = mock_sb.table.return_value.select.return_value
        calls = [str(c) for c in select_chain.eq.call_args_list]
        assert any("task_id" in c or "task-abc" in c for c in calls)

    def test_clear_deletes_by_task_id(self):
        """clear() must issue a DELETE filtered by task_id."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        cp.clear()

        mock_sb.table.assert_called_with("analysis_checkpoints")
        delete_chain = mock_sb.table.return_value.delete.return_value
        delete_chain.eq.assert_called_with("task_id", "task-abc")

    def test_clear_non_fatal_on_error(self):
        """clear() must not raise if Supabase fails."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.side_effect = Exception("timeout")

        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "NVDA")
        cp.clear()  # must not raise

    def test_ticker_uppercased_in_save(self):
        """SupabaseCheckpoint must store uppercase ticker regardless of input."""
        mock_sb = self._mock_supabase()
        state = _sample_state(ticker="nvda")
        cp = SupabaseCheckpoint(mock_sb, "task-abc", "user-123", "nvda")
        cp.save(state)

        upsert_call = mock_sb.table.return_value.upsert.call_args
        assert upsert_call[0][0]["ticker"] == "NVDA"


# ── get_checkpoint factory ─────────────────────────────────────────────────

class TestGetCheckpoint:
    def test_returns_supabase_checkpoint_when_client_provided(self, tmp_path):
        mock_sb = MagicMock()
        cp = get_checkpoint("task-1", "NVDA", "2026-01-15", "user-1", supabase_client=mock_sb)
        assert isinstance(cp, SupabaseCheckpoint)

    def test_returns_local_checkpoint_when_no_client(self, tmp_path):
        cp = get_checkpoint(
            "task-1", "NVDA", "2026-01-15", "cli",
            supabase_client=None,
            cache_dir=str(tmp_path),
        )
        assert isinstance(cp, LocalCheckpoint)

    def test_returns_local_checkpoint_when_client_is_none_explicitly(self, tmp_path):
        cp = get_checkpoint(
            "task-1", "NVDA", "2026-01-15",
            supabase_client=None,
            cache_dir=str(tmp_path),
        )
        assert isinstance(cp, LocalCheckpoint)

    def test_supabase_checkpoint_has_correct_task_id(self, tmp_path):
        mock_sb = MagicMock()
        cp = get_checkpoint("my-task-id", "NVDA", "2026-01-15", "user-1", supabase_client=mock_sb)
        assert isinstance(cp, SupabaseCheckpoint)
        assert cp._task_id == "my-task-id"

    def test_local_checkpoint_uses_provided_cache_dir(self, tmp_path):
        cp = get_checkpoint(
            "task-1", "NVDA", "2026-01-15", "cli",
            supabase_client=None,
            cache_dir=str(tmp_path),
        )
        assert isinstance(cp, LocalCheckpoint)
        # The checkpoint path must be inside the provided cache dir
        assert str(tmp_path) in str(cp._path)
