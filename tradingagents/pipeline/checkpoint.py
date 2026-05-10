"""Lightweight checkpoint — saves pipeline state after each phase.

In SaaS mode: uses Firestore (per-user, per-task).
In CLI mode: uses a local JSON file (same directory as cache).
No LangGraph dependency.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from tradingagents.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)


class LocalCheckpoint:
    """File-based checkpoint for CLI use."""

    def __init__(self, cache_dir: str, ticker: str, date: str, user_id: str = "cli"):
        safe_ticker = ticker.upper().replace("/", "_")
        self._path = Path(cache_dir) / "checkpoints" / f"{user_id}_{safe_ticker}_{date}.json"
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


class FirestoreCheckpoint:
    """Firestore-based checkpoint for SaaS use."""

    def __init__(self, supabase_client, task_id: str):
        # Using Firestore directly if available, otherwise no-op
        self._client = supabase_client
        self._task_id = task_id

    def save(self, state: AnalysisState) -> None:
        # In SaaS mode, state is tracked in the analyses table via analysis_worker
        # This checkpoint is a no-op — the worker handles progress tracking
        pass

    def load(self) -> Optional[AnalysisState]:
        return None

    def clear(self) -> None:
        pass
