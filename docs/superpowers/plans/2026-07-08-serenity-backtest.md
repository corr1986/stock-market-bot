# Serenity Signals FASE 1 (Backtest) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backtest 12 mesi della strategia "Serenity fresh-ticker": BUY quando Serenity menziona un ticker nuovo (o silente da ≥30gg) con stance bullish conviction ≥4, exit Chandelier, parametri identici a v3.

**Architecture:** Tre moduli nuovi nel repo `stock-market-bot`: `serenity_data.py` (parsing archivio tweet + eventi freshness), `serenity_stance.py` (classificazione Groq con cache su disco), `backtest_serenity.py` (simulazione con position_sizing riusato + metriche). Zero modifiche a v1/v3.

**Tech Stack:** Python, pytest, groq (`llama-3.3-70b-versatile`), yfinance, pandas. Spec: `docs/superpowers/specs/2026-07-08-serenity-signals-design.md`.

**Directory di lavoro:** `C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot`

**Note operative:**
- Eseguire pytest SOLO sui file di test nominati (mai sull'intera repo di altri progetti).
- L'archivio tweet è già clonato in scratchpad; per l'esecuzione reale si riclonerà `yan-labs/serenity-aleabitoreddit` (shallow) in una cartella temporanea.
- Semplificazione documentata FASE 1: niente earnings-filter storico e niente SELL anticipato su stance bearish nel backtest (entrambi restano nel design del bot live). Va riportata nel report finale.

---

### Task 1: Estrazione menzioni ticker (`serenity_data.py`)

**Files:**
- Create: `serenity_data.py`
- Test: `tests/test_serenity_data.py`

- [ ] **Step 1: Scrivi il test che fallisce**

```python
# tests/test_serenity_data.py
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
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `python -m pytest tests/test_serenity_data.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'serenity_data'`

- [ ] **Step 3: Implementazione minima**

```python
# serenity_data.py
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
```

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `python -m pytest tests/test_serenity_data.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add serenity_data.py tests/test_serenity_data.py
git commit -m "feat(serenity): estrazione menzioni cashtag da tweet"
```

---

### Task 2: Caricamento archivio tweet (`load_tweets`)

**Files:**
- Modify: `serenity_data.py`
- Test: `tests/test_serenity_data.py`

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi a `tests/test_serenity_data.py`:

```python
import json
from serenity_data import load_tweets


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
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `python -m pytest tests/test_serenity_data.py -v`
Expected: FAIL con `ImportError: cannot import name 'load_tweets'`

- [ ] **Step 3: Implementazione minima**

Aggiungi a `serenity_data.py`:

```python
import json
from datetime import datetime


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
```

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `python -m pytest tests/test_serenity_data.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add serenity_data.py tests/test_serenity_data.py
git commit -m "feat(serenity): caricamento archivio tweet ordinato"
```

---

### Task 3: Eventi freshness (`build_fresh_events`)

**Files:**
- Modify: `serenity_data.py`
- Test: `tests/test_serenity_data.py`

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi a `tests/test_serenity_data.py`:

```python
from datetime import datetime, timezone
from serenity_data import build_fresh_events


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


def test_events_sorted_by_date_across_tickers():
    tweets = [
        _tw("1", "$AAA", "2026-02-01T10:00:00+00:00"),
        _tw("2", "$BBB", "2026-01-01T10:00:00+00:00"),
    ]
    events = build_fresh_events(tweets)
    assert [e["ticker"] for e in events] == ["BBB", "AAA"]
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `python -m pytest tests/test_serenity_data.py -v`
Expected: FAIL con `ImportError: cannot import name 'build_fresh_events'`

- [ ] **Step 3: Implementazione minima**

Aggiungi a `serenity_data.py`:

```python
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
```

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `python -m pytest tests/test_serenity_data.py -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add serenity_data.py tests/test_serenity_data.py
git commit -m "feat(serenity): eventi freshness (prima menzione o gap >=30gg)"
```

---

### Task 4: Classificazione stance con Groq e cache (`serenity_stance.py`)

**Files:**
- Create: `serenity_stance.py`
- Test: `tests/test_serenity_stance.py`

- [ ] **Step 1: Scrivi il test che fallisce**

```python
# tests/test_serenity_stance.py
import json
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


def test_cache_roundtrip(tmp_path):
    path = str(tmp_path / "cache.json")
    save_cache({"K": {"stance": "bullish", "conviction": 4}}, path)
    assert load_cache(path) == {"K": {"stance": "bullish", "conviction": 4}}


def test_load_cache_missing_file_returns_empty(tmp_path):
    assert load_cache(str(tmp_path / "nope.json")) == {}
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `python -m pytest tests/test_serenity_stance.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'serenity_stance'`

- [ ] **Step 3: Implementazione minima**

```python
# serenity_stance.py
"""Classificazione stance (bullish/bearish/neutral) dei tweet di Serenity via Groq.

Il modello e' una costante: per passare a Claude Haiku basta cambiare
STANCE_MODEL e il client nel chiamante. Cache su disco per non riclassificare.
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
    cache[key] = None
    return None
```

Nota: il client Groq reale viene creato dal chiamante (`backtest_serenity.py`) con `Groq(api_key=GROQ_API_KEY)` — il modulo non importa `groq` a livello top per restare testabile senza dipendenze.

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `python -m pytest tests/test_serenity_stance.py -v`
Expected: 11 PASS

- [ ] **Step 5: Commit**

```bash
git add serenity_stance.py tests/test_serenity_stance.py
git commit -m "feat(serenity): classificazione stance Groq con cache e retry"
```

---

### Task 5: Motore di simulazione — trade singolo (`backtest_serenity.py`)

**Files:**
- Create: `backtest_serenity.py`
- Test: `tests/test_serenity_backtest.py`

Il motore riusa `position_sizing.calculate_size` e `calculate_chandelier_stop` (rischio default 40 EUR — passare `risk_target=40.0` esplicito perché il default del modulo è 100).

- [ ] **Step 1: Scrivi il test che fallisce**

```python
# tests/test_serenity_backtest.py
from datetime import date

import pandas as pd

from backtest_serenity import compute_atr, simulate_trade


def _df(rows):
    """rows: list of (date_str, open, high, low, close)"""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame(
        {"Open": [r[1] for r in rows], "High": [r[2] for r in rows],
         "Low": [r[3] for r in rows], "Close": [r[4] for r in rows]},
        index=idx,
    )


def test_compute_atr_constant_range():
    # 20 giorni con range costante 2.0 e nessun gap -> ATR(14) = 2.0
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(1, 21)]
    atr = compute_atr(_df(rows), period=14)
    assert abs(atr.iloc[-1] - 2.0) < 1e-9


def test_simulate_trade_stop_hit():
    # entry al primo giorno dopo l'evento: open=100, ATR costante 2 -> SL iniziale = 96
    # il prezzo scende sotto 96 il 2026-02-05 -> exit a 96
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(2, 31)]
    rows += [
        ("2026-02-02", 100, 101, 99, 100),   # entry day (open 100)
        ("2026-02-03", 100, 101, 99, 100),
        ("2026-02-04", 100, 101, 99, 100),
        ("2026-02-05", 97, 97, 90, 91),      # low 90 < stop 96 -> exit
    ]
    trade = simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0)
    assert trade is not None
    assert trade["entry_date"] == date(2026, 2, 2)
    assert abs(trade["entry"] - 100.0) < 1e-9
    assert trade["exit_date"] == date(2026, 2, 5)
    assert abs(trade["exit"] - 96.0) < 1e-9   # stop = 100 - 2*2
    # size = risk / sl_pct = 40 / 0.04 = 1000 EUR; pnl = -4% * 1000 = -40 EUR
    assert abs(trade["size_eur"] - 1000.0) < 1e-6
    assert abs(trade["pnl_eur"] - (-40.0)) < 1e-6


def test_simulate_trade_chandelier_trails_up():
    # il prezzo sale: il chandelier segue il max high e l'exit avviene in profitto
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(2, 31)]
    rows += [
        ("2026-02-02", 100, 101, 99, 100),    # entry open 100, stop 96
        ("2026-02-03", 104, 110, 103, 109),   # max_high 110 -> stop 106
        ("2026-02-04", 108, 109, 105, 106),   # low 105 < stop 106 -> exit 106
    ]
    trade = simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0)
    assert abs(trade["exit"] - 106.0) < 1e-9
    assert trade["pnl_eur"] > 0


def test_simulate_trade_gap_down_exits_at_open():
    # gap sotto lo stop: exit realistico all'open, non allo stop
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(2, 31)]
    rows += [
        ("2026-02-02", 100, 101, 99, 100),   # entry, stop 96
        ("2026-02-03", 90, 92, 88, 91),      # open 90 < stop 96 -> exit a 90
    ]
    trade = simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0)
    assert abs(trade["exit"] - 90.0) < 1e-9


def test_simulate_trade_still_open_closes_at_last_close():
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(2, 31)]
    rows += [
        ("2026-02-02", 100, 101, 99, 100),
        ("2026-02-03", 100, 101, 99.5, 100.5),
    ]
    trade = simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0)
    assert trade["exit_date"] == date(2026, 2, 3)
    assert trade["open_at_end"] is True


def test_simulate_trade_insufficient_history_returns_none():
    rows = [("2026-02-02", 100, 101, 99, 100)]  # niente storico per ATR
    assert simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0) is None
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `python -m pytest tests/test_serenity_backtest.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backtest_serenity'`

- [ ] **Step 3: Implementazione minima**

```python
# backtest_serenity.py
"""Backtest FASE 1 strategia Serenity fresh-ticker.

Regole (spec docs/superpowers/specs/2026-07-08-serenity-signals-design.md):
- evento freshness + stance bullish conviction >= 4 -> BUY all'open del giorno dopo
- SL iniziale 2xATR(14), trailing Chandelier (riuso position_sizing), no TP
- rischio 40 EUR/trade, max 3 posizioni, VIX>30 blocca entry (get_regime_config)
Semplificazioni FASE 1 (documentate): niente earnings filter storico,
niente SELL anticipato su stance bearish.
"""
from datetime import timedelta

import pandas as pd

from position_sizing import calculate_size, calculate_chandelier_stop, SL_MULT

RISK_EUR = 40.0
BALANCE_START = 20000.0
MAX_POSITIONS = 3
ATR_PERIOD = 14
MIN_CONVICTION = 4


def compute_atr(df, period=ATR_PERIOD):
    """ATR classico (media mobile semplice del True Range)."""
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def simulate_trade(df, event_date, risk_eur=RISK_EUR):
    """Simula un singolo trade long dall'evento all'exit Chandelier.

    df: OHLC giornaliero (index datetime). Entry: open del primo giorno di borsa
    successivo a event_date. Ritorna dict trade o None se dati insufficienti.
    """
    atr = compute_atr(df)
    future = df[df.index.date > event_date]
    if future.empty:
        return None
    entry_idx = future.index[0]
    pos = df.index.get_loc(entry_idx)
    atr_entry = atr.iloc[pos - 1] if pos >= 1 else float("nan")
    if pd.isna(atr_entry) or atr_entry <= 0:
        return None

    entry = float(df.loc[entry_idx, "Open"])
    initial_sl = entry - SL_MULT * atr_entry
    size_eur = calculate_size(entry, atr_entry, risk_target=risk_eur)

    stop = initial_sl
    max_high = entry
    exit_price = None
    exit_date = None
    open_at_end = False

    path = df.iloc[pos:]
    for ts, row in path.iterrows():
        if float(row["Open"]) < stop:          # gap sotto lo stop
            exit_price, exit_date = float(row["Open"]), ts.date()
            break
        if float(row["Low"]) <= stop and ts != entry_idx:
            exit_price, exit_date = stop, ts.date()
            break
        max_high = max(max_high, float(row["High"]))
        stop = calculate_chandelier_stop(max_high, atr_entry, initial_sl)

    if exit_price is None:                     # ancora aperto a fine dati
        last = path.iloc[-1]
        exit_price, exit_date = float(last["Close"]), path.index[-1].date()
        open_at_end = True

    pnl_pct = (exit_price - entry) / entry
    return {
        "entry_date": entry_idx.date(),
        "entry": entry,
        "exit_date": exit_date,
        "exit": exit_price,
        "size_eur": size_eur,
        "pnl_eur": pnl_pct * size_eur,
        "pnl_pct": pnl_pct * 100,
        "open_at_end": open_at_end,
    }
```

Nota sul primo giorno: lo stop non può scattare sul `Low` del giorno di entry (l'SL viene piazzato dopo l'apertura) ma il check sul gap resta.

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `python -m pytest tests/test_serenity_backtest.py -v`
Expected: 6 PASS

- [ ] **Step 5: Verifica che i test v3 esistenti non siano rotti (nessuna modifica a file condivisi, ma check economico)**

Run: `python -m pytest tests/ -v --collect-only -q | tail -3`
Expected: solo collezione, nessun errore di import.

- [ ] **Step 6: Commit**

```bash
git add backtest_serenity.py tests/test_serenity_backtest.py
git commit -m "feat(serenity): motore simulazione trade con ATR e Chandelier"
```

---

### Task 6: Portafoglio — concorrenza max 3 posizioni + filtro VIX (`run_backtest`)

**Files:**
- Modify: `backtest_serenity.py`
- Test: `tests/test_serenity_backtest.py`

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi a `tests/test_serenity_backtest.py`:

```python
from backtest_serenity import run_backtest


def _flat_df(start="2026-01-02", days=60, price=100.0):
    idx = pd.bdate_range(start, periods=days)
    return pd.DataFrame(
        {"Open": price, "High": price + 1, "Low": price - 1, "Close": price},
        index=idx,
    )


def _sig(ticker, d):
    return {"ticker": ticker, "date": d,
            "stance": {"stance": "bullish", "conviction": 5}}


def test_run_backtest_respects_max_positions():
    # 4 segnali lo stesso giorno, prezzi piatti (nessuna exit) -> solo 3 trade
    prices = {t: _flat_df() for t in ["AAA", "BBB", "CCC", "DDD"]}
    vix = pd.Series(15.0, index=_flat_df().index)
    signals = [_sig(t, date(2026, 2, 2)) for t in ["AAA", "BBB", "CCC", "DDD"]]
    trades = run_backtest(signals, prices, vix)
    assert len(trades) == 3


def test_run_backtest_vix_blocks_entry():
    prices = {"AAA": _flat_df()}
    idx = _flat_df().index
    vix = pd.Series(35.0, index=idx)  # risk-off
    trades = run_backtest([_sig("AAA", date(2026, 2, 2))], prices, vix)
    assert trades == []


def test_run_backtest_skips_low_conviction_and_non_bullish():
    prices = {"AAA": _flat_df(), "BBB": _flat_df()}
    vix = pd.Series(15.0, index=_flat_df().index)
    signals = [
        {"ticker": "AAA", "date": date(2026, 2, 2),
         "stance": {"stance": "bullish", "conviction": 3}},
        {"ticker": "BBB", "date": date(2026, 2, 2),
         "stance": {"stance": "bearish", "conviction": 5}},
    ]
    assert run_backtest(signals, prices, vix) == []


def test_run_backtest_missing_prices_skipped():
    vix = pd.Series(15.0, index=_flat_df().index)
    assert run_backtest([_sig("ZZZ", date(2026, 2, 2))], {}, vix) == []
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `python -m pytest tests/test_serenity_backtest.py -v`
Expected: FAIL con `ImportError: cannot import name 'run_backtest'`

- [ ] **Step 3: Implementazione minima**

Aggiungi a `backtest_serenity.py`:

```python
from position_sizing import get_regime_config


def _vix_at(vix, day):
    """Ultimo valore VIX disponibile <= day (None se nessuno)."""
    subset = vix[vix.index.date <= day]
    return float(subset.iloc[-1]) if len(subset) else None


def run_backtest(signals, prices, vix, risk_eur=RISK_EUR, max_positions=MAX_POSITIONS):
    """Simula tutti i segnali in ordine cronologico rispettando la concorrenza.

    signals: [{ticker, date, stance: {stance, conviction}}]
    prices: dict ticker -> DataFrame OHLC giornaliero
    vix: Series di chiusure ^VIX
    Ritorna lista trade (dict di simulate_trade + ticker/event_date).
    """
    open_until = []  # exit_date dei trade aperti
    trades = []
    for sig in sorted(signals, key=lambda s: s["date"]):
        stance = sig.get("stance") or {}
        if stance.get("stance") != "bullish" or stance.get("conviction", 0) < MIN_CONVICTION:
            continue
        df = prices.get(sig["ticker"])
        if df is None or df.empty:
            continue
        v = _vix_at(vix, sig["date"])
        if v is None or not get_regime_config(v)["allow_entry"]:
            continue

        trade = simulate_trade(df, sig["date"], risk_eur=risk_eur)
        if trade is None:
            continue
        # concorrenza: conta i trade ancora aperti alla data di entry
        open_until = [d for d in open_until if d >= trade["entry_date"]]
        if len(open_until) >= max_positions:
            continue
        open_until.append(trade["exit_date"])
        trade.update({"ticker": sig["ticker"], "event_date": sig["date"]})
        trades.append(trade)
    return trades
```

Nota: `get_regime_config` limita anche `max_positions` a 2 nel regime "cautious" (VIX 20-30); per semplicità FASE 1 il limite dinamico non viene applicato — solo il blocco entry a VIX>30. Documentato nel report.

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `python -m pytest tests/test_serenity_backtest.py -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add backtest_serenity.py tests/test_serenity_backtest.py
git commit -m "feat(serenity): run_backtest con max posizioni e filtro VIX"
```

---

### Task 7: Metriche (`compute_metrics`)

**Files:**
- Modify: `backtest_serenity.py`
- Test: `tests/test_serenity_backtest.py`

- [ ] **Step 1: Scrivi il test che fallisce**

Aggiungi a `tests/test_serenity_backtest.py`:

```python
from backtest_serenity import compute_metrics


def test_compute_metrics_basic():
    trades = [
        {"pnl_eur": 100.0, "exit_date": date(2026, 1, 10)},
        {"pnl_eur": -40.0, "exit_date": date(2026, 1, 20)},
        {"pnl_eur": 60.0, "exit_date": date(2026, 2, 1)},
    ]
    m = compute_metrics(trades, balance_start=20000.0)
    assert m["n_trades"] == 3
    assert abs(m["win_rate"] - (2 / 3 * 100)) < 1e-6
    assert abs(m["total_pnl_eur"] - 120.0) < 1e-6
    assert abs(m["return_pct"] - 0.6) < 1e-6
    # max drawdown: equity 20100 -> 20060 -> 20120; picco 20100, valle 20060
    assert abs(m["max_drawdown_pct"] - (40.0 / 20100 * 100)) < 1e-6


def test_compute_metrics_empty():
    m = compute_metrics([], balance_start=20000.0)
    assert m["n_trades"] == 0
    assert m["win_rate"] == 0.0
```

- [ ] **Step 2: Esegui il test e verifica che fallisca**

Run: `python -m pytest tests/test_serenity_backtest.py -v`
Expected: FAIL con `ImportError: cannot import name 'compute_metrics'`

- [ ] **Step 3: Implementazione minima**

Aggiungi a `backtest_serenity.py`:

```python
def compute_metrics(trades, balance_start=BALANCE_START):
    """Metriche aggregate sull'equity curve ordinata per data di exit."""
    if not trades:
        return {"n_trades": 0, "win_rate": 0.0, "total_pnl_eur": 0.0,
                "return_pct": 0.0, "max_drawdown_pct": 0.0}
    ordered = sorted(trades, key=lambda t: t["exit_date"])
    wins = sum(1 for t in ordered if t["pnl_eur"] > 0)
    total = sum(t["pnl_eur"] for t in ordered)

    equity = balance_start
    peak = balance_start
    max_dd = 0.0
    for t in ordered:
        equity += t["pnl_eur"]
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

    return {
        "n_trades": len(ordered),
        "win_rate": wins / len(ordered) * 100,
        "total_pnl_eur": total,
        "return_pct": total / balance_start * 100,
        "max_drawdown_pct": max_dd * 100,
    }
```

- [ ] **Step 4: Esegui il test e verifica che passi**

Run: `python -m pytest tests/test_serenity_backtest.py -v`
Expected: 12 PASS

- [ ] **Step 5: Commit**

```bash
git add backtest_serenity.py tests/test_serenity_backtest.py
git commit -m "feat(serenity): metriche backtest (WR, pnl, max drawdown)"
```

---

### Task 8: Runner principale (main) — dati reali

**Files:**
- Modify: `backtest_serenity.py`
- Modify: `.gitignore` (aggiungi `serenity_stance_cache.json` e `serenity_repo/`)

Nessun nuovo unit test: il main orchestra funzioni già testate + I/O di rete (Groq, yfinance, git clone). La verifica è l'esecuzione reale del Task 9.

- [ ] **Step 1: Implementa il main**

Aggiungi in coda a `backtest_serenity.py`:

```python
def _download_prices(tickers, start, end):
    """Scarica OHLC daily per ticker via yfinance. Ritorna dict ticker->df (skip mancanti)."""
    import yfinance as yf
    prices = {}
    for t in tickers:
        try:
            df = yf.download(t, start=start, end=end, interval="1d",
                             progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) >= ATR_PERIOD + 2:
                prices[t] = df
        except Exception as e:
            print(f"  skip {t}: {e}")
    return prices


def main():
    import argparse
    import subprocess
    import tempfile
    import os
    from datetime import timedelta

    import yfinance as yf
    from groq import Groq

    from config import GROQ_API_KEY
    from serenity_data import load_tweets, build_fresh_events
    from serenity_stance import classify_event, load_cache, save_cache, CACHE_PATH

    parser = argparse.ArgumentParser()
    parser.add_argument("--tweets", help="path aleabitoreddit_tweets.json (default: clona il repo)")
    parser.add_argument("--limit", type=int, default=0, help="max eventi da classificare (0=tutti)")
    args = parser.parse_args()

    # 1. archivio tweet
    if args.tweets:
        tweets_path = args.tweets
    else:
        tmp = os.path.join(tempfile.gettempdir(), "serenity_repo")
        if not os.path.exists(tmp):
            subprocess.run(["git", "clone", "--depth", "1",
                            "https://github.com/yan-labs/serenity-aleabitoreddit.git", tmp],
                           check=True)
        else:
            subprocess.run(["git", "-C", tmp, "pull"], check=False)
        tweets_path = os.path.join(tmp, "data", "aleabitoreddit_tweets.json")

    tweets = load_tweets(tweets_path)
    events = build_fresh_events(tweets)
    print(f"Tweet: {len(tweets)} | Eventi freshness: {len(events)}")
    if args.limit:
        events = events[:args.limit]

    # 2. classificazione stance (cache su disco, resume-safe)
    client = Groq(api_key=GROQ_API_KEY)
    cache = load_cache()
    signals = []
    for i, e in enumerate(events):
        stance = classify_event(e, client, cache)
        if stance:
            signals.append({"ticker": e["ticker"], "date": e["date"], "stance": stance})
        if (i + 1) % 25 == 0:
            save_cache(cache)
            print(f"  classificati {i + 1}/{len(events)}")
    save_cache(cache)
    bullish = [s for s in signals
               if s["stance"]["stance"] == "bullish" and s["stance"]["conviction"] >= MIN_CONVICTION]
    print(f"Segnali bullish conviction>={MIN_CONVICTION}: {len(bullish)}")

    # 3. prezzi + VIX
    start = min(s["date"] for s in bullish) - timedelta(days=60)
    end = max(t["date"].date() for t in tweets) + timedelta(days=1)
    tickers = sorted({s["ticker"] for s in bullish})
    print(f"Download prezzi per {len(tickers)} ticker...")
    prices = _download_prices(tickers, start, end)
    vix_df = yf.download("^VIX", start=start, end=end, interval="1d", progress=False)
    if isinstance(vix_df.columns, pd.MultiIndex):
        vix_df.columns = vix_df.columns.get_level_values(0)
    vix = vix_df["Close"]

    # 4. simulazione + report
    trades = run_backtest(bullish, prices, vix)
    m = compute_metrics(trades)
    print("\n=== BACKTEST SERENITY (FASE 1) ===")
    print(f"Trade: {m['n_trades']} | WR: {m['win_rate']:.1f}% | "
          f"PnL: {m['total_pnl_eur']:+.0f} EUR ({m['return_pct']:+.2f}%) | "
          f"MaxDD: {m['max_drawdown_pct']:.2f}%")
    still_open = sum(1 for t in trades if t.get("open_at_end"))
    print(f"Posizioni ancora aperte a fine periodo: {still_open}")

    out = pd.DataFrame(trades)
    out.to_csv("backtest_serenity_trades.csv", index=False)
    print("Trade salvati in backtest_serenity_trades.csv")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Aggiorna `.gitignore`**

Aggiungi le righe:

```
serenity_stance_cache.json
```

(La cache contiene solo classificazioni, ma è grande e rigenerabile — se si preferisce committarla per riproducibilità, decidere al Task 9.)

- [ ] **Step 3: Verifica sintassi e import**

Run: `python -c "import backtest_serenity; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backtest_serenity.py .gitignore
git commit -m "feat(serenity): runner backtest end-to-end (clone repo, Groq, yfinance)"
```

---

### Task 9: Esecuzione reale e report

**Files:**
- Output: `backtest_serenity_trades.csv`, report in chat + `Dev Log.md`

- [ ] **Step 1: Smoke test con 20 eventi**

Run: `python backtest_serenity.py --limit 20`
Expected: stampa conteggi, nessuna eccezione. Verificare a occhio 2-3 classificazioni nella cache (`serenity_stance_cache.json`) rileggendo i tweet corrispondenti.

- [ ] **Step 2: Esecuzione completa**

Run: `python backtest_serenity.py`
Expected: completa (con la cache, i re-run sono quasi istantanei). Se Groq free tier limita le richieste giornaliere, rilanciare il giorno dopo: la cache riprende da dove era arrivata.

- [ ] **Step 3: Sanity check risultati**

- Controllare 5 trade a campione in `backtest_serenity_trades.csv` contro i grafici reali (entry/exit plausibili).
- Verificare che i ticker più citati (NBIS, SIVE, AXTI...) compaiano tra gli eventi con date coerenti con `ticker_stats.txt` del repo sorgente.

- [ ] **Step 4: Report all'utente (GATE)**

Presentare: n. trade, WR%, rendimento, MaxDD, confronto con v1/v3, semplificazioni applicate (no earnings filter storico, no bearish exit, no limite dinamico posizioni in regime cautious, survivorship su ticker senza dati yfinance). **La decisione se costruire la FASE 2 (bot live) spetta all'utente.**

- [ ] **Step 5: Commit finale + aggiornamento Dev Log**

```bash
git add backtest_serenity_trades.csv "Dev Log.md"
git commit -m "feat(serenity): risultati backtest FASE 1"
git push
```

---

## Self-review

- **Copertura spec:** §1 fonte dati → Task 8 (clone + load); §2 segnali → Task 3, 4, 6 (freshness, stance, filtri); §3 portafoglio → Task 5, 6 (sizing, chandelier, max pos); §5 backtest+gate → Task 9; §6 error handling → retry/None-cache in Task 4, skip ticker in Task 8; §7 testing → tutti i task TDD. §4 (workflow/cron) è FASE 2, fuori scope di questo piano per il gate.
- **Semplificazioni dichiarate:** earnings filter storico, bearish exit, max_positions dinamico nel regime cautious — tutte annotate e riportate nel report del Task 9.
- **Coerenza tipi:** `build_fresh_events` produce `{ticker, date, tweet_ids, texts}` consumato da `classify_event`; i segnali `{ticker, date, stance}` prodotti nel main sono il formato atteso da `run_backtest`. `simulate_trade` usa `event_date` come `datetime.date`, coerente con `e["date"]` (date) dei fresh events.
