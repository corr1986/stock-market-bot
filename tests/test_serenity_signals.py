import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date

from serenity_signals import (
    select_bullish, select_bearish_tickers, bearish_after, MIN_CONVICTION,
)


def test_bearish_after_only_counts_later_stance():
    # bearish di maggio PRECEDE il segnale di giugno -> NON deve triggerare
    events = [
        {"ticker": "CBRS", "date": date(2026, 5, 14), "tweet_ids": ["a"], "texts": [""]},
        {"ticker": "CBRS", "date": date(2026, 6, 27), "tweet_ids": ["b"], "texts": [""]},
    ]
    cache = {
        "CBRS:a": {"stance": "bearish", "conviction": 4},
        "CBRS:b": {"stance": "bullish", "conviction": 4},
    }
    # ingresso su segnale del 27/06: la bearish del 14/05 è vecchia -> False
    assert bearish_after(events, cache, "CBRS", after=date(2026, 6, 27)) is False


def test_bearish_after_triggers_on_later_bearish():
    events = [
        {"ticker": "NBIS", "date": date(2026, 3, 1), "tweet_ids": ["a"], "texts": [""]},
        {"ticker": "NBIS", "date": date(2026, 4, 10), "tweet_ids": ["b"], "texts": [""]},
    ]
    cache = {
        "NBIS:a": {"stance": "bullish", "conviction": 5},
        "NBIS:b": {"stance": "bearish", "conviction": 5},
    }
    # ingresso 01/03, bearish successiva 10/04 -> True
    assert bearish_after(events, cache, "NBIS", after=date(2026, 3, 1)) is True


def test_bearish_after_ignores_low_conviction():
    events = [{"ticker": "X", "date": date(2026, 4, 1), "tweet_ids": ["a"], "texts": [""]}]
    cache = {"X:a": {"stance": "bearish", "conviction": 3}}
    assert bearish_after(events, cache, "X", after=date(2026, 3, 1)) is False


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
