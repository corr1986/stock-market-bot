"""Parsing archivio tweet Serenity (@aleabitoreddit) ed eventi freshness.

Fonte dati: repo GitHub yan-labs/serenity-aleabitoreddit,
file data/aleabitoreddit_tweets.json (aggiornato ogni ora).
Spec: docs/superpowers/specs/2026-07-08-serenity-signals-design.md
"""
import re

MENTION_RE = re.compile(r"\$([A-Z]{1,5})\b")


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
