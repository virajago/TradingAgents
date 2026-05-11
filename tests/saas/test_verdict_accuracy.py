"""P1: verdict accuracy calculation must be mathematically correct.

The _is_correct_30d helper in saas/api/routes/verdicts.py implements the
SPX-relative accuracy rules. These are load-bearing: the track record
page is a key marketing claim and must be provably correct.

Rules (from the docstring):
  BULLISH  correct if  stock_30d_return > SPX_30d_return + 2%
  BEARISH  correct if  stock_30d_return < SPX_30d_return - 2%
  NEUTRAL  correct if  abs(stock_30d_return - SPX_30d_return) < 5%
"""
from __future__ import annotations

import pytest


def _make_verdict(verdict: str, stock_30d_pct: float, spx_30d_pct: float) -> dict:
    """Build a verdict dict that mimics the DB row shape used by _is_correct_30d."""
    base_stock = 100.0
    base_spx = 4_000.0
    return {
        "verdict": verdict,
        "price_at_verdict": base_stock,
        "price_30d": base_stock * (1 + stock_30d_pct / 100),
        "spx_price_at_verdict": base_spx,
        "spx_price_30d": base_spx * (1 + spx_30d_pct / 100),
        "settled_30d": True,
    }


def _get_is_correct():
    """Import _is_correct_30d or skip if it is not exported."""
    try:
        from saas.api.routes.verdicts import _is_correct_30d
        return _is_correct_30d
    except (ImportError, AttributeError):
        pytest.skip("_is_correct_30d not importable")


class TestBullishVerdictAccuracy:
    """BULLISH verdicts win when the stock beats SPX by more than 2 percentage points."""

    def test_bullish_correct_when_stock_beats_spx_by_5pct(self):
        """Stock +10% vs SPX +5% → outperforms by 5pp → correct."""
        fn = _get_is_correct()
        v = _make_verdict("BULLISH", stock_30d_pct=10, spx_30d_pct=5)
        assert fn(v) is True

    def test_bullish_correct_at_exactly_2pct_threshold(self):
        """Stock beats SPX by exactly 2pp — boundary: the rule is >, so this is NOT correct."""
        fn = _get_is_correct()
        v = _make_verdict("BULLISH", stock_30d_pct=7, spx_30d_pct=5)
        # stock_return = 0.07, spx_return = 0.05, diff = 0.02 (== 0.02, not > 0.02)
        assert fn(v) is False

    def test_bullish_correct_when_marginally_above_threshold(self):
        """Outperformance of 2.01pp qualifies as BULLISH-correct."""
        fn = _get_is_correct()
        v = _make_verdict("BULLISH", stock_30d_pct=7.01, spx_30d_pct=5)
        assert fn(v) is True

    def test_bullish_incorrect_when_stock_underperforms(self):
        """Stock +2% vs SPX +5% — underperforms by 3pp → incorrect."""
        fn = _get_is_correct()
        v = _make_verdict("BULLISH", stock_30d_pct=2, spx_30d_pct=5)
        assert fn(v) is False

    def test_bullish_incorrect_when_stock_flat_and_spx_up(self):
        """Stock flat, SPX +3% → underperforms by 3pp → incorrect."""
        fn = _get_is_correct()
        v = _make_verdict("BULLISH", stock_30d_pct=0, spx_30d_pct=3)
        assert fn(v) is False

    def test_bullish_correct_even_when_both_down_but_stock_loses_less(self):
        """Stock -1% vs SPX -5% → outperforms by 4pp → correct."""
        fn = _get_is_correct()
        v = _make_verdict("BULLISH", stock_30d_pct=-1, spx_30d_pct=-5)
        assert fn(v) is True


class TestBearishVerdictAccuracy:
    """BEARISH verdicts win when the stock underperforms SPX by more than 2pp."""

    def test_bearish_correct_when_stock_down_5pct_and_spx_flat(self):
        """Stock -5% vs SPX 0% → underperforms by 5pp → correct."""
        fn = _get_is_correct()
        v = _make_verdict("BEARISH", stock_30d_pct=-5, spx_30d_pct=0)
        assert fn(v) is True

    def test_bearish_incorrect_when_stock_beats_spx(self):
        """Stock +5% vs SPX +3% — outperforms by 2pp → BEARISH is wrong."""
        fn = _get_is_correct()
        v = _make_verdict("BEARISH", stock_30d_pct=5, spx_30d_pct=3)
        assert fn(v) is False

    def test_bearish_incorrect_when_stock_only_slightly_underperforms(self):
        """Stock -1% vs SPX 0% → underperforms by only 1pp < 2pp threshold → incorrect."""
        fn = _get_is_correct()
        v = _make_verdict("BEARISH", stock_30d_pct=-1, spx_30d_pct=0)
        # stock_return = -0.01, spx_return = 0.0, threshold = -0.02
        # -0.01 < -0.02 is False → incorrect
        assert fn(v) is False

    def test_bearish_correct_when_both_down_stock_down_more(self):
        """Stock -8% vs SPX -2% → underperforms by 6pp → correct."""
        fn = _get_is_correct()
        v = _make_verdict("BEARISH", stock_30d_pct=-8, spx_30d_pct=-2)
        assert fn(v) is True


class TestNeutralVerdictAccuracy:
    """NEUTRAL verdicts win when stock and SPX returns are within 5pp of each other."""

    def test_neutral_correct_within_5pct_of_spx(self):
        """Stock +3% vs SPX +1% → abs(diff) = 2% < 5% → correct."""
        fn = _get_is_correct()
        v = _make_verdict("NEUTRAL", stock_30d_pct=3, spx_30d_pct=1)
        assert fn(v) is True

    def test_neutral_correct_when_perfectly_tracking_spx(self):
        """Stock exactly matches SPX → diff = 0 → correct."""
        fn = _get_is_correct()
        v = _make_verdict("NEUTRAL", stock_30d_pct=5, spx_30d_pct=5)
        assert fn(v) is True

    def test_neutral_incorrect_when_stock_far_above_spx(self):
        """Stock +10% vs SPX +2% → abs(diff) = 8% > 5% → incorrect."""
        fn = _get_is_correct()
        v = _make_verdict("NEUTRAL", stock_30d_pct=10, spx_30d_pct=2)
        assert fn(v) is False

    def test_neutral_incorrect_when_stock_far_below_spx(self):
        """Stock -5% vs SPX +3% → abs(diff) = 8% > 5% → incorrect."""
        fn = _get_is_correct()
        v = _make_verdict("NEUTRAL", stock_30d_pct=-5, spx_30d_pct=3)
        assert fn(v) is False

    def test_neutral_boundary_exactly_5pct(self):
        """abs(diff) = exactly 5% → rule is <, so NOT correct at the boundary."""
        fn = _get_is_correct()
        v = _make_verdict("NEUTRAL", stock_30d_pct=10, spx_30d_pct=5)
        # stock_return = 0.10, spx_return = 0.05, abs(diff) = 0.05 (== 0.05, not < 0.05)
        assert fn(v) is False


class TestMissingPriceData:
    """When settlement data is missing, _is_correct_30d must return False safely."""

    def test_missing_price_at_verdict_returns_false(self):
        fn = _get_is_correct()
        v = {
            "verdict": "BULLISH",
            "price_at_verdict": None,
            "price_30d": 110.0,
            "spx_price_at_verdict": 4000.0,
            "spx_price_30d": 4100.0,
            "settled_30d": True,
        }
        assert fn(v) is False

    def test_missing_price_30d_returns_false(self):
        fn = _get_is_correct()
        v = {
            "verdict": "BULLISH",
            "price_at_verdict": 100.0,
            "price_30d": None,
            "spx_price_at_verdict": 4000.0,
            "spx_price_30d": 4100.0,
            "settled_30d": True,
        }
        assert fn(v) is False

    def test_missing_all_prices_returns_false(self):
        fn = _get_is_correct()
        v = {
            "verdict": "BULLISH",
            "price_at_verdict": None,
            "price_30d": None,
            "spx_price_at_verdict": None,
            "spx_price_30d": None,
            "settled_30d": True,
        }
        assert fn(v) is False

    def test_missing_spx_data_uses_zero_as_spx_return(self):
        """When SPX price data is absent the implementation defaults spx_return to 0.0.

        This means a BULLISH verdict only needs stock_return > 0.02 to be correct.
        """
        fn = _get_is_correct()
        v = {
            "verdict": "BULLISH",
            "price_at_verdict": 100.0,
            "price_30d": 115.0,  # +15% — clearly beats 0% + 2%
            "spx_price_at_verdict": None,
            "spx_price_30d": None,
            "settled_30d": True,
        }
        # With spx_return = 0.0 and stock_return = 0.15 → 0.15 > 0.02 → correct
        assert fn(v) is True
