import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from serenity_data import extract_mentions


def test_extract_mentions_basic():
    text = "Long $NBIS here, also watching $AXTI and $NBIS again"
    assert extract_mentions(text) == ["NBIS", "AXTI"]


def test_extract_mentions_ignores_lowercase_and_long():
    # $btc minuscolo e $TOOLONG (>5 lettere) non sono cashtag validi
    assert extract_mentions("$btc $TOOLONG $MU") == ["MU"]


def test_extract_mentions_empty_and_none():
    assert extract_mentions("") == []
    assert extract_mentions(None) == []
