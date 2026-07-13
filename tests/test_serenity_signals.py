import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date

from serenity_signals import select_bullish, select_bearish_tickers, MIN_CONVICTION


def _events():
    return [
        {"ticker": "NBIS", "date": date(2026, 3, 1), "tweet_ids": ["1"], "texts": ["a"]},
        {"ticker": "AXTI", "date": date(2026, 3, 5), "tweet_ids": ["2"], "texts": ["b"]},
        {"ticker": "OLD",  "date": date(2026, 1, 1), "tweet_ids": ["3"], "texts": ["c"]},
        {"ticker": "WEAK", "date": date(2026, 3, 5), "tweet_ids": ["4"], "texts": ["d"]},
        {"ticker": "BEAR", "date": date(2026, 3, 6), "tweet_ids": ["5"], "texts": ["e"]},
    ]


def _cache():
    return {
        "NBIS:1": {"stance": "bullish", "conviction": 5},
        "AXTI:2": {"stance": "bullish", "conviction": 4},
        "OLD:3":  {"stance": "bullish", "conviction": 5},   # troppo vecchio
        "WEAK:4": {"stance": "bullish", "conviction": 3},   # conviction bassa
        "BEAR:5": {"stance": "bearish", "conviction": 5},
    }


def test_select_bullish_recent_and_strong():
    sigs = select_bullish(_events(), _cache(), since=date(2026, 3, 1))
    tickers = [s["ticker"] for s in sigs]
    assert tickers == ["NBIS", "AXTI"]   # OLD escluso (vecchio), WEAK (conv 3), BEAR (bearish)


def test_select_bullish_since_filters_old():
    sigs = select_bullish(_events(), _cache(), since=date(2026, 3, 4))
    assert [s["ticker"] for s in sigs] == ["AXTI"]   # NBIS del 01/03 escluso


def test_select_bullish_skips_uncached():
    events = _events()
    events.append({"ticker": "NEW", "date": date(2026, 3, 7), "tweet_ids": ["9"], "texts": ["x"]})
    sigs = select_bullish(events, _cache(), since=date(2026, 3, 1))
    assert "NEW" not in [s["ticker"] for s in sigs]   # non in cache -> ignorato


def test_select_bearish_tickers():
    bears = select_bearish_tickers(_events(), _cache(), since=date(2026, 3, 1))
    assert bears == {"BEAR"}


def test_select_bearish_respects_since():
    bears = select_bearish_tickers(_events(), _cache(), since=date(2026, 3, 10))
    assert bears == set()


def test_min_conviction_is_4():
    assert MIN_CONVICTION == 4
