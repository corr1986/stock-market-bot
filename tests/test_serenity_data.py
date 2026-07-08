import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import json
from datetime import datetime
from serenity_data import extract_mentions, load_tweets, build_fresh_events


def _tw(id_, text, iso):
    return {"id": id_, "text": text, "date": datetime.fromisoformat(iso)}


def test_first_mention_is_fresh_event():
    tweets = [_tw("1", "new name $SIVE", "2025-12-23T10:00:00+00:00")]
    events = build_fresh_events(tweets)
    assert len(events) == 1
    e = events[0]
    assert e["ticker"] == "SIVE"
    assert e["date"].isoformat() == "2025-12-23"
    assert e["tweet_ids"] == ["1"]


def test_same_day_tweets_grouped_into_one_event():
    tweets = [
        _tw("1", "$SIVE thesis", "2025-12-23T10:00:00+00:00"),
        _tw("2", "$SIVE more detail", "2025-12-23T15:00:00+00:00"),
    ]
    events = build_fresh_events(tweets)
    assert len(events) == 1
    assert events[0]["tweet_ids"] == ["1", "2"]
    assert len(events[0]["texts"]) == 2


def test_mention_within_gap_is_not_fresh():
    tweets = [
        _tw("1", "$SIVE thesis", "2025-12-23T10:00:00+00:00"),
        _tw("2", "$SIVE update", "2026-01-05T10:00:00+00:00"),  # 13 giorni dopo
    ]
    events = build_fresh_events(tweets, gap_days=30)
    assert len(events) == 1  # solo la prima menzione


def test_mention_after_gap_is_fresh_again():
    tweets = [
        _tw("1", "$SIVE thesis", "2025-12-23T10:00:00+00:00"),
        _tw("2", "$SIVE is back", "2026-03-01T10:00:00+00:00"),  # 68 giorni dopo
    ]
    events = build_fresh_events(tweets, gap_days=30)
    assert [e["date"].isoformat() for e in events] == ["2025-12-23", "2026-03-01"]


def test_consecutive_mentions_keep_ticker_not_fresh():
    # menzioni ogni 20 giorni: last_seen si aggiorna anche se non fresh
    tweets = [
        _tw("1", "$SIVE a", "2026-01-01T10:00:00+00:00"),
        _tw("2", "$SIVE b", "2026-01-21T10:00:00+00:00"),
        _tw("3", "$SIVE c", "2026-02-10T10:00:00+00:00"),  # 40gg dalla prima, 20 dalla seconda
    ]
    events = build_fresh_events(tweets, gap_days=30)
    assert len(events) == 1


def test_events_sorted_by_date_across_tickers():
    tweets = [
        _tw("1", "$AAA", "2026-02-01T10:00:00+00:00"),
        _tw("2", "$BBB", "2026-01-01T10:00:00+00:00"),
    ]
    events = build_fresh_events(tweets)
    assert [e["ticker"] for e in events] == ["BBB", "AAA"]


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
