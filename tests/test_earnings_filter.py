from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytest


def _mock_ticker(days_to_earnings):
    m = MagicMock()
    if days_to_earnings is None:
        m.calendar = {}
    else:
        m.calendar = {"Earnings Date": [datetime.now() + timedelta(days=days_to_earnings)]}
    return m


def test_earnings_within_window_returns_true():
    with patch("earnings_filter.yf.Ticker", return_value=_mock_ticker(7)):
        from earnings_filter import has_earnings_soon
        assert has_earnings_soon("AAPL", days=14) is True


def test_earnings_outside_window_returns_false():
    with patch("earnings_filter.yf.Ticker", return_value=_mock_ticker(30)):
        from earnings_filter import has_earnings_soon
        assert has_earnings_soon("AAPL", days=14) is False


def test_no_earnings_data_returns_false():
    with patch("earnings_filter.yf.Ticker", return_value=_mock_ticker(None)):
        from earnings_filter import has_earnings_soon
        assert has_earnings_soon("AAPL", days=14) is False


def test_exception_returns_false():
    with patch("earnings_filter.yf.Ticker", side_effect=Exception("network error")):
        from earnings_filter import has_earnings_soon
        assert has_earnings_soon("AAPL", days=14) is False
