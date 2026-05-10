"""Lightweight checkpoint — saves pipeline state after each phase.

In SaaS mode: uses Supabase Postgres (per-user, per-task) via the
  analysis_checkpoints table. Allows crash recovery for 5-min analyses.
In CLI mode: uses a local JSON file under the cache directory.
No LangGraph dependency.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from tradingagents.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)


class LocalCheckpoint:
    """File-based checkpoint for CLI use.

    Stores state as JSON at:
      {cache_dir}/checkpoints/{user_id}_{TICKER}_{date}.json
    """

    def __init__(self, cache_dir: str, ticker: str, date: str, user_id: str = "cli"):
        safe_ticker = ticker.upper().replace("/", "_")
        self._path = (
            Path(cache_dir) / "checkpoints" / f"{user_id}_{safe_ticker}_{date}.json"
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, state: AnalysisState) -> None:
        try:
            self._path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Checkpoint save failed: %s", e)

    def load(self) -> Optional[AnalysisState]:
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return AnalysisState(**data)
        except Exception as e:
            logger.warning("Checkpoint load failed: %s", e)
            return None

    def clear(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except Exception:
            pass


class SupabaseCheckpoint:
    """Supabase Postgres checkpoint for SaaS use.

    Uses the `analysis_checkpoints` table (service-role key bypasses RLS):

        CREATE TABLE analysis_checkpoints (
            task_id   text PRIMARY KEY,
            user_id   uuid NOT NULL,
            ticker    text NOT NULL,
            state     jsonb NOT NULL,
            phase     integer NOT NULL DEFAULT 0,
            updated_at timestamptz DEFAULT now()
        );

    Allows the analysis worker to resume from the last completed phase
    if the Cloud Run instance is recycled mid-analysis.
    """

    def __init__(self, supabase_client, task_id: str, user_id: str, ticker: str):
        self._sb = supabase_client
        self._task_id = task_id
        self._user_id = str(user_id)
        self._ticker = ticker.upper()

    def save(self, state: AnalysisState) -> None:
        """Upsert current pipeline state to Postgres."""
        completed = len(state.completed_agents)
        try:
            self._sb.table("analysis_checkpoints").upsert({
                "task_id": self._task_id,
                "user_id": self._user_id,
                "ticker": self._ticker,
                "state": asdict(state),
                "phase": completed,
            }, on_conflict="task_id").execute()
        except Exception as e:
            # Non-fatal — analysis continues even if checkpoint fails
            logger.warning("Supabase checkpoint save failed for %s: %s", self._task_id, e)

    def load(self) -> Optional[AnalysisState]:
        """Load a prior checkpoint if one exists for this task."""
        try:
            result = (
                self._sb.table("analysis_checkpoints")
                .select("state")
                .eq("task_id", self._task_id)
                .eq("user_id", self._user_id)
                .single()
                .execute()
            )
            if result.data:
                return AnalysisState(**result.data["state"])
        except Exception as e:
            logger.warning("Supabase checkpoint load failed for %s: %s", self._task_id, e)
        return None

    def clear(self) -> None:
        """Delete checkpoint after successful analysis completion."""
        try:
            self._sb.table("analysis_checkpoints").delete().eq(
                "task_id", self._task_id
            ).execute()
        except Exception as e:
            logger.warning("Supabase checkpoint clear failed for %s: %s", self._task_id, e)


def get_checkpoint(
    task_id: str,
    ticker: str,
    date: str,
    user_id: str = "cli",
    supabase_client=None,
    cache_dir: str = "~/.tradingagents/cache",
):
    """Factory — returns the right checkpoint backend for the context."""
    if supabase_client is not None:
        return SupabaseCheckpoint(supabase_client, task_id, user_id, ticker)
    return LocalCheckpoint(cache_dir, ticker, date, user_id)
