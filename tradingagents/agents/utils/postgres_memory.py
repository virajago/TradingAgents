"""
Per-user Postgres-backed memory log for SaaS use.
Drop-in replacement for TradingMemoryLog in server contexts.
Each user's decision history is isolated — no cross-contamination.
"""
from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


class PostgresMemoryLog:
    """
    Stores trading decisions and reflections in Postgres, scoped by user_id.
    Uses the Supabase service-role client (bypasses RLS — runs in server context).

    Interface mirrors TradingMemoryLog so TradingAgentsGraph can use either
    interchangeably by checking for a 'supabase_client' in config.
    """

    def __init__(self, user_id: str, supabase_client) -> None:
        self._user_id = user_id
        self._sb = supabase_client

    def store_decision(self, ticker: str, trade_date: str, final_trade_decision: str) -> None:
        """Upsert a pending decision for this user+ticker+date."""
        from tradingagents.agents.utils.rating import parse_rating
        rating = parse_rating(final_trade_decision)

        # Idempotent: ignore if already exists
        self._sb.table("memory_log").upsert({
            "user_id": self._user_id,
            "ticker": ticker.upper(),
            "trade_date": trade_date,
            "rating": rating,
            "status": "pending",
            "decision_text": final_trade_decision,
        }, on_conflict="user_id,ticker,trade_date", ignore_duplicates=True).execute()

    def load_entries(self) -> List[dict]:
        """Load all memory entries for this user, ordered newest first."""
        result = self._sb.table("memory_log").select("*").eq(
            "user_id", self._user_id
        ).order("created_at", desc=True).execute()
        return result.data or []

    def get_pending_entries(self) -> List[dict]:
        """Return entries with status=pending.

        Keys are normalised to match TradingMemoryLog's dict shape so that
        _resolve_pending_entries() in trading_graph.py works with both backends:
          "date"     <- trade_date
          "decision" <- decision_text
          "ticker"   <- ticker (unchanged)
        """
        result = self._sb.table("memory_log").select("*").eq(
            "user_id", self._user_id
        ).eq("status", "pending").order("created_at", desc=True).execute()
        rows = result.data or []
        return [
            {
                **row,
                "date": str(row.get("trade_date", "")),
                "decision": row.get("decision_text", ""),
                "pending": True,
            }
            for row in rows
        ]

    def store_reflection(self, ticker: str, trade_date: str, reflection: str) -> None:
        """Mark a pending entry as resolved with a reflection."""
        self._sb.table("memory_log").update({
            "status": "resolved",
            "reflection_text": reflection,
            "resolved_at": "now()",
        }).eq("user_id", self._user_id).eq(
            "ticker", ticker.upper()
        ).eq("trade_date", trade_date).execute()

    def get_past_context(self, ticker: str, n_same: int = 5, n_cross: int = 3) -> str:
        """Return formatted past context string for agent prompt injection."""
        entries = [e for e in self.load_entries() if e.get("status") == "resolved"]
        if not entries:
            return ""

        same, cross = [], []
        for e in entries:
            if len(same) >= n_same and len(cross) >= n_cross:
                break
            if e["ticker"] == ticker.upper() and len(same) < n_same:
                same.append(e)
            elif e["ticker"] != ticker.upper() and len(cross) < n_cross:
                cross.append(e)

        if not same and not cross:
            return ""

        parts = []
        if same:
            parts.append(f"Past analyses of {ticker} (most recent first):")
            for e in same:
                tag = f"[{e['trade_date']} | {e['ticker']} | {e.get('rating', 'Hold')}]"
                decision_snippet = (e.get("decision_text") or "")[:300]
                reflection = e.get("reflection_text") or ""
                entry_parts = [tag, f"DECISION:\n{decision_snippet}"]
                if reflection:
                    entry_parts.append(f"REFLECTION:\n{reflection}")
                parts.append("\n\n".join(entry_parts))
        if cross:
            parts.append("Recent cross-ticker lessons:")
            for e in cross:
                tag = f"[{e['trade_date']} | {e['ticker']} | {e.get('rating', 'Hold')}]"
                reflection = e.get("reflection_text") or (e.get("decision_text") or "")[:300]
                parts.append(f"{tag}\n{reflection}")

        return "\n\n".join(parts)

    def batch_update_with_outcomes(self, updates: List[dict]) -> None:
        """Resolve multiple pending entries with outcomes and reflections.

        Each element must have keys: ticker, trade_date, raw_return, alpha_return,
        holding_days, reflection.
        """
        for upd in updates:
            try:
                self._sb.table("memory_log").update({
                    "status": "resolved",
                    "reflection_text": upd["reflection"],
                    "resolved_at": "now()",
                }).eq("user_id", self._user_id).eq(
                    "ticker", upd["ticker"].upper()
                ).eq("trade_date", upd["trade_date"]).execute()
            except Exception as exc:
                logger.warning(
                    "Failed to resolve memory_log entry %s/%s: %s",
                    upd["ticker"], upd["trade_date"], exc,
                )

    def format_for_prompt(self, limit: int = 10) -> str:
        """
        Format recent memory entries as a string for injection into LLM prompts.
        Returns empty string if no entries (safe to include in any prompt).
        """
        entries = self.load_entries()[:limit]
        if not entries:
            return ""

        lines = ["## Your recent trading decisions (for context):"]
        for e in entries:
            status_str = f"[{e['status'].upper()}]"
            line = f"- {e['trade_date']} | {e['ticker']} | {e.get('rating', 'N/A')} | {status_str}"
            if e.get("reflection_text"):
                line += f" — {e['reflection_text'][:100]}"
            lines.append(line)
        return "\n".join(lines)
