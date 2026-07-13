"""Selezione segnali live dalla cache stance + eventi freshness.

Funzioni pure e testabili: la classificazione dei nuovi eventi via Groq viene
fatta dagli orchestratori (serenity_daily.py) prima di chiamare queste.

- select_bullish: eventi bullish freschi conv>=4 con data >= 'since' (candidati BUY)
- select_bearish_tickers: ticker con stance bearish conv>=4 recente (trigger di exit)
"""

MIN_CONVICTION = 4


def _stance(event, cache):
    return cache.get(f"{event['ticker']}:{event['tweet_ids'][0]}")


def select_bullish(events, cache, since):
    """Segnali BUY: eventi freschi bullish conv>=MIN_CONVICTION con date >= since.

    Ritorna [{ticker, date}] in ordine cronologico. Eventi non in cache: ignorati.
    """
    out = []
    for e in events:
        if e["date"] < since:
            continue
        st = _stance(e, cache)
        if st and st["stance"] == "bullish" and st["conviction"] >= MIN_CONVICTION:
            out.append({"ticker": e["ticker"], "date": e["date"]})
    out.sort(key=lambda s: s["date"])
    return out


def select_bearish_tickers(events, cache, since):
    """Ticker con stance bearish conv>=MIN_CONVICTION e date >= since (per gli exit)."""
    bears = set()
    for e in events:
        if e["date"] < since:
            continue
        st = _stance(e, cache)
        if st and st["stance"] == "bearish" and st["conviction"] >= MIN_CONVICTION:
            bears.add(e["ticker"])
    return bears
