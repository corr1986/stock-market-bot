import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import json
from serenity_data import extract_mentions, load_tweets


def _write_archive(tmp_path, items):
    p = tmp_path / "tweets.json"
    p.write_text(json.dumps(items), encoding="utf-8")
    return str(p)


def test_load_tweets_sorted_ascending(tmp_path):
    path = _write_archive(tmp_path, [
        {"id": "2", "text": "$MU up", "createdAtISO": "2026-07-07T19:49:55+00:00"},
        {"id": "1", "text": "$NBIS new", "createdAtISO": "2025-07-21T10:00:00+00:00"},
    ])
    tweets = load_tweets(path)
    assert [t["id"] for t in tweets] == ["1", "2"]
    assert tweets[0]["date"].year == 2025


def test_load_tweets_skips_missing_date(tmp_path):
    path = _write_archive(tmp_path, [
        {"id": "1", "text": "no date"},
        {"id": "2", "text": "$MU", "createdAtISO": "2026-01-01T00:00:00+00:00"},
    ])
    tweets = load_tweets(path)
    assert len(tweets) == 1 and tweets[0]["id"] == "2"


def test_extract_mentions_basic():
    text = "Long $NBIS here, also watching $AXTI and $NBIS again"
    assert extract_mentions(text) == ["NBIS", "AXTI"]


def test_extract_mentions_ignores_lowercase_and_long():
    # $btc minuscolo e $TOOLONG (>5 lettere) non sono cashtag validi
    assert extract_mentions("$btc $TOOLONG $MU") == ["MU"]


def test_extract_mentions_empty_and_none():
    assert extract_mentions("") == []
    assert extract_mentions(None) == []
