"""Test per analyzer: robustezza di compute_indicators e build_market_snapshot."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from analyzer import compute_indicators, build_market_snapshot


def _valid_df(n=60) -> pd.DataFrame:
    """DataFrame OHLCV sintetico con n righe e prezzi variabili."""
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    close = np.linspace(100, 120, n) + np.sin(np.arange(n))
    return pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )


# ── compute_indicators ──────────────────────────────────────────────────────

def test_compute_indicators_valid_df_returns_indicators():
    ind = compute_indicators(_valid_df(60))
    assert isinstance(ind, dict)
    assert ind["rsi_14"] is not None
    assert "macd_hist" in ind and "atr_14" in ind


def test_compute_indicators_raises_on_single_row():
    # 1 riga: prima causava AttributeError ('numpy.float64' has no attribute 'diff')
    # perché .squeeze() collassava la Series in uno scalare.
    with pytest.raises(ValueError):
        compute_indicators(_valid_df(1))


def test_compute_indicators_raises_on_insufficient_rows():
    # < 50 righe: indicatori come SMA50 non calcolabili in modo affidabile.
    with pytest.raises(ValueError):
        compute_indicators(_valid_df(30))


# ── build_market_snapshot resiliente ────────────────────────────────────────

@patch("analyzer.WATCHLIST_INDICES", {})
@patch("analyzer.WATCHLIST_EUROPE", [])
@patch("analyzer.WATCHLIST_USA", ["GOOD", "BAD"])
@patch("analyzer.compute_indicators")
@patch("analyzer.fetch_data")
def test_build_market_snapshot_skips_failing_ticker(mock_fetch, mock_compute):
    # Un ticker che fa fallire compute_indicators NON deve bloccare gli altri.
    mock_fetch.return_value = pd.DataFrame({"Close": [1.0]})
    mock_compute.side_effect = [ValueError("boom"), {"price": 100.0}]
    snap = build_market_snapshot()
    assert "GOOD" not in snap["USA"]              # fallito → skippato
    assert snap["USA"]["BAD"] == {"price": 100.0}  # valido → presente
