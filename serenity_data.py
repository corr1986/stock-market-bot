"""Parsing archivio tweet Serenity (@aleabitoreddit) ed eventi freshness.

Fonte dati: repo GitHub yan-labs/serenity-aleabitoreddit,
file data/aleabitoreddit_tweets.json (aggiornato ogni ora).
Spec: docs/superpowers/specs/2026-07-08-serenity-signals-design.md
"""
import json
import re
from datetime import datetime

MENTION_RE = re.compile(r"\$([A-Z]{1,5})\b")


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
