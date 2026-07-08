import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from serenity_stance import parse_stance_response, classify_event, load_cache, save_cache


def test_parse_valid_response():
    raw = '{"stance": "bullish", "conviction": 5}'
    assert parse_stance_response(raw) == {"stance": "bullish", "conviction": 5}


def test_parse_response_with_prose_around_json():
    raw = 'Ecco la risposta: {"stance": "bearish", "conviction": 4} spero aiuti'
    assert parse_stance_response(raw) == {"stance": "bearish", "conviction": 4}


def test_parse_invalid_stance_returns_none():
    assert parse_stance_response('{"stance": "mega-bull", "conviction": 5}') is None


def test_parse_invalid_conviction_returns_none():
    assert parse_stance_response('{"stance": "bullish", "conviction": 9}') is None
    assert parse_stance_response('{"stance": "bullish"}') is None


def test_parse_garbage_returns_none():
    assert parse_stance_response("non e' json") is None
    assert parse_stance_response("") is None
    assert parse_stance_response(None) is None


class FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class FakeClient:
    """Client Groq finto: risponde con contenuti predefiniti e conta le chiamate."""
    def __init__(self, contents):
        self._contents = list(contents)
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls += 1
        content = self._contents.pop(0)
        if isinstance(content, Exception):
            raise content
        return type("R", (), {"choices": [FakeChoice(content)]})()


def _event():
    return {"ticker": "SIVE", "date": None,
            "tweet_ids": ["123"], "texts": ["$SIVE is the next bottleneck"]}


def test_classify_event_calls_llm_and_caches():
    client = FakeClient(['{"stance": "bullish", "conviction": 5}'])
    cache = {}
    result = classify_event(_event(), client, cache)
    assert result == {"stance": "bullish", "conviction": 5}
    assert cache["SIVE:123"] == result
    assert client.calls == 1


def test_classify_event_uses_cache_without_calling_llm():
    client = FakeClient([])
    cache = {"SIVE:123": {"stance": "neutral", "conviction": 2}}
    result = classify_event(_event(), client, cache)
    assert result == {"stance": "neutral", "conviction": 2}
    assert client.calls == 0


def test_classify_event_unparsable_cached_as_none():
    client = FakeClient(["boh"])
    cache = {}
    assert classify_event(_event(), client, cache) is None
    assert cache["SIVE:123"] is None


def test_classify_event_retries_on_exception(monkeypatch):
    import serenity_stance
    monkeypatch.setattr(serenity_stance.time, "sleep", lambda s: None)
    client = FakeClient([RuntimeError("rate limit"),
                         '{"stance": "bullish", "conviction": 4}'])
    cache = {}
    result = classify_event(_event(), client, cache)
    assert result == {"stance": "bullish", "conviction": 4}
    assert client.calls == 2


def test_cache_roundtrip(tmp_path):
    path = str(tmp_path / "cache.json")
    save_cache({"K": {"stance": "bullish", "conviction": 4}}, path)
    assert load_cache(path) == {"K": {"stance": "bullish", "conviction": 4}}


def test_load_cache_missing_file_returns_empty(tmp_path):
    assert load_cache(str(tmp_path / "nope.json")) == {}
