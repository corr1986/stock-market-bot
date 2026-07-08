"""Classificazione stance (bullish/bearish/neutral) dei tweet di Serenity via Groq.

Il modello e' una costante: per passare a Claude Haiku basta cambiare
STANCE_MODEL e il client nel chiamante. Cache su disco per non riclassificare.
Spec: docs/superpowers/specs/2026-07-08-serenity-signals-design.md
"""
import json
import os
import time

STANCE_MODEL = "llama-3.3-70b-versatile"
CACHE_PATH = "serenity_stance_cache.json"
MAX_RETRIES = 3

SYSTEM_PROMPT = (
    "You are a financial analyst. You are given tweets by the analyst Serenity "
    "(@aleabitoreddit) that mention one stock ticker. Classify Serenity's stance "
    "on that ticker. Respond ONLY with JSON: "
    '{"stance": "bullish|bearish|neutral", "conviction": 1-5}. '
    "bullish = suggests upside/accumulation; bearish = criticism/downside risk; "
    "neutral = informational only. conviction 5 = strongest explicit conviction."
)


def parse_stance_response(raw):
    """Estrae {stance, conviction} dalla risposta LLM. None se non valida."""
    if not raw:
        return None
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end])
        stance = data.get("stance")
        conviction = int(data["conviction"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    if stance not in ("bullish", "bearish", "neutral") or not 1 <= conviction <= 5:
        return None
    return {"stance": stance, "conviction": conviction}


def load_cache(path=CACHE_PATH):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache, path=CACHE_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)


def classify_event(event, client, cache):
    """Classifica un evento freshness. Ritorna {stance, conviction} o None.

    Cache key: TICKER:primo_tweet_id (stabile tra i run).
    Anche il risultato 'non parsabile' (None) viene cachato per non riprovare.
    """
    key = f"{event['ticker']}:{event['tweet_ids'][0]}"
    if key in cache:
        return cache[key]

    text_block = "\n---\n".join(event["texts"])[:6000]
    user = f"Ticker: ${event['ticker']}\nTweets:\n{text_block}"

    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=STANCE_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                max_tokens=60,
                temperature=0.0,
            )
            result = parse_stance_response(resp.choices[0].message.content)
            cache[key] = result
            return result
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(5 * (2 ** attempt))
    # errore API persistente (quota, rete): NON cachare, un run futuro riprovera'
    return None
