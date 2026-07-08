"""Parsing archivio tweet Serenity (@aleabitoreddit) ed eventi freshness.

Fonte dati: repo GitHub yan-labs/serenity-aleabitoreddit,
file data/aleabitoreddit_tweets.json (aggiornato ogni ora).
Spec: docs/superpowers/specs/2026-07-08-serenity-signals-design.md
"""
import json
import re
from datetime import datetime

MENTION_RE = re.compile(r"\$([A-Z]{1,5})\b")
FRESHNESS_GAP_DAYS = 30


def build_fresh_events(tweets, gap_days=FRESHNESS_GAP_DAYS):
    """Eventi 'ticker fresco': prima menzione assoluta, o ritorno dopo >= gap_days di silenzio.

    Un evento per (ticker, giorno); la menzione NON fresca aggiorna comunque last_seen.
    Ritorna [{ticker, date, tweet_ids, texts}] ordinato per data.
    """
    by_ticker_day = {}
    for tw in tweets:
        day = tw["date"].date()
        for ticker in extract_mentions(tw["text"]):
            by_ticker_day.setdefault(ticker, {}).setdefault(day, []).append(tw)

    events = []
    for ticker, days in by_ticker_day.items():
        prev = None
        for day in sorted(days):
            if prev is None or (day - prev).days >= gap_days:
                tws = days[day]
                events.append({
                    "ticker": ticker,
                    "date": day,
                    "tweet_ids": [t["id"] for t in tws],
                    "texts": [t["text"] for t in tws],
                })
            prev = day
    events.sort(key=lambda e: (e["date"], e["ticker"]))
    return events


def load_tweets(path):
    """Carica l'archivio JSON e ritorna [{id, text, date}] ordinato per data crescente."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    tweets = []
    for t in raw:
        iso = t.get("createdAtISO")
        if not iso:
            continue
        tweets.append({
            "id": t["id"],
            "text": t.get("text", ""),
            "date": datetime.fromisoformat(iso),
        })
    tweets.sort(key=lambda x: x["date"])
    return tweets


def extract_mentions(text):
    """Ticker unici menzionati come $CASHTAG, in ordine di apparizione."""
    if not text:
        return []
    seen, out = set(), []
    for m in MENTION_RE.finditer(text):
        ticker = m.group(1)
        if ticker not in seen:
            seen.add(ticker)
            out.append(ticker)
    return out
