# Stock Market Bot v3 — Piano di Implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire v3 parallela a v1 con Chandelier Exit, regime VIX, sizing dinamico, earnings filter e analyst consensus.

**Architecture:** File separati (`main_v3.py`, `tracker_v3.py`, `claude_analyst_v3.py`, `earnings_filter.py`, `position_sizing.py`). Portfolio in `portfolio_v3.json`. v1 intatta.

**Tech Stack:** Python, yfinance, Groq API (llama-3.3-70b-versatile), pytest, ta, pandas

---

## File map

| File | Azione | Responsabilità |
|---|---|---|
| `earnings_filter.py` | Crea | `has_earnings_soon(ticker, days) -> bool` |
| `position_sizing.py` | Crea | `calculate_size()`, `calculate_chandelier_stop()`, `get_regime_config()` |
| `claude_analyst_v3.py` | Crea | LLM con analyst consensus, restituisce `List[dict]` |
| `tracker_v3.py` | Crea | Chandelier monitoring orario, legge/scrive `portfolio_v3.json` |
| `main_v3.py` | Crea | Entry point lunedì, orchestra tutti i moduli v3 |
| `tests/test_earnings_filter.py` | Crea | Unit test earnings filter |
| `tests/test_position_sizing.py` | Crea | Unit test sizing + chandelier + regime |
| `tests/test_tracker_v3.py` | Crea | Unit test logica chandelier in tracker |
| `portfolio_v3.json` | Crea (runtime) | Generato da `main_v3.py` al primo avvio |

Riusati senza modifiche: `analyzer.py`, `macro_analyzer.py`, `news_fetcher.py`, `notifier.py`, `config.py`

---

## Task 1: earnings_filter.py

**Files:**
- Crea: `earnings_filter.py`
- Crea: `tests/test_earnings_filter.py`

- [ ] **Step 1: Crea la directory tests se non esiste**
```bash
mkdir -p "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\tests"
```

- [ ] **Step 2: Scrivi il test**

`tests/test_earnings_filter.py`:
```python
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytest

def _mock_ticker(days_to_earnings):
    m = MagicMock()
    if days_to_earnings is None:
        m.calendar = {}
    else:
        m.calendar = {"Earnings Date": [datetime.now() + timedelta(days=days_to_earnings)]}
    return m

def test_earnings_within_window_returns_true():
    with patch("earnings_filter.yf.Ticker", return_value=_mock_ticker(7)):
        from earnings_filter import has_earnings_soon
        assert has_earnings_soon("AAPL", days=14) is True

def test_earnings_outside_window_returns_false():
    with patch("earnings_filter.yf.Ticker", return_value=_mock_ticker(30)):
        from earnings_filter import has_earnings_soon
        assert has_earnings_soon("AAPL", days=14) is False

def test_no_earnings_data_returns_false():
    with patch("earnings_filter.yf.Ticker", return_value=_mock_ticker(None)):
        from earnings_filter import has_earnings_soon
        assert has_earnings_soon("AAPL", days=14) is False

def test_exception_returns_false():
    with patch("earnings_filter.yf.Ticker", side_effect=Exception("network error")):
        from earnings_filter import has_earnings_soon
        assert has_earnings_soon("AAPL", days=14) is False
```

- [ ] **Step 3: Esegui — deve fallire**
```bash
cd "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot"
venv\Scripts\python -m pytest tests/test_earnings_filter.py -v
```
Atteso: `ModuleNotFoundError: No module named 'earnings_filter'`

- [ ] **Step 4: Implementa `earnings_filter.py`**
```python
from datetime import datetime, timedelta
import yfinance as yf


def has_earnings_soon(ticker: str, days: int = 14) -> bool:
    """True se il ticker ha earnings entro `days` giorni. False su errore o dati mancanti."""
    try:
        cal = yf.Ticker(ticker).calendar
        if not cal or "Earnings Date" not in cal:
            return False
        dates = cal["Earnings Date"]
        if not dates:
            return False
        cutoff = datetime.now() + timedelta(days=days)
        return any(d <= cutoff for d in dates if hasattr(d, 'year'))
    except Exception:
        return False
```

- [ ] **Step 5: Esegui — deve passare**
```bash
venv\Scripts\python -m pytest tests/test_earnings_filter.py -v
```
Atteso: `4 passed`

- [ ] **Step 6: Commit**
```bash
git init  # se non già repo git
git add earnings_filter.py tests/test_earnings_filter.py
git commit -m "feat: add earnings_filter with 14-day window"
```

---

## Task 2: position_sizing.py

**Files:**
- Crea: `position_sizing.py`
- Crea: `tests/test_position_sizing.py`

- [ ] **Step 1: Scrivi i test**

`tests/test_position_sizing.py`:
```python
from position_sizing import calculate_size, calculate_chandelier_stop, get_regime_config

# --- calculate_size ---

def test_size_average_atr():
    # entry=100, atr=2.5 → sl_pct=5% → size=40/0.05=800
    assert calculate_size(100.0, 2.5) == 800.0

def test_size_low_atr_capped():
    # entry=100, atr=0.5 → sl_pct=1% → size=4000 → capped=1500
    assert calculate_size(100.0, 0.5) == 1500.0

def test_size_high_atr_floored():
    # entry=100, atr=25.0 → sl_pct=50% → size=80 → floor=100
    assert calculate_size(100.0, 25.0) == 100.0

# --- calculate_chandelier_stop ---

def test_chandelier_above_initial_sl():
    # max_high=110, atr=2.5 → trail=110-5=105 > initial_sl=95
    assert calculate_chandelier_stop(110.0, 2.5, 95.0) == 105.0

def test_chandelier_below_initial_sl_returns_sl():
    # max_high=100, atr=2.5 → trail=95 == initial_sl=95
    assert calculate_chandelier_stop(100.0, 2.5, 95.0) == 95.0

def test_chandelier_never_below_initial_sl():
    # max_high=96, atr=2.5 → trail=91 < initial_sl=95 → return 95
    assert calculate_chandelier_stop(96.0, 2.5, 95.0) == 95.0

# --- get_regime_config ---

def test_regime_risk_on():
    cfg = get_regime_config(15.0)
    assert cfg["allow_entry"] is True
    assert cfg["max_positions"] == 3

def test_regime_cautious():
    cfg = get_regime_config(22.5)
    assert cfg["allow_entry"] is True
    assert cfg["max_positions"] == 2

def test_regime_risk_off():
    cfg = get_regime_config(28.0)
    assert cfg["allow_entry"] is False
```

- [ ] **Step 2: Esegui — deve fallire**
```bash
venv\Scripts\python -m pytest tests/test_position_sizing.py -v
```
Atteso: `ModuleNotFoundError: No module named 'position_sizing'`

- [ ] **Step 3: Implementa `position_sizing.py`**
```python
SL_MULT          = 2.0
RISK_TARGET_EUR  = 40.0
MAX_POSITION_EUR = 1500.0
MIN_POSITION_EUR = 100.0


def calculate_size(
    entry_price: float,
    atr_entry: float,
    risk_target: float = RISK_TARGET_EUR,
    max_size: float = MAX_POSITION_EUR,
    sl_mult: float = SL_MULT,
) -> float:
    """Posizione in EUR a rischio costante."""
    sl_pct = (sl_mult * atr_entry) / entry_price
    if sl_pct <= 0:
        return MIN_POSITION_EUR
    size = risk_target / sl_pct
    return max(MIN_POSITION_EUR, min(size, max_size))


def calculate_chandelier_stop(
    max_high: float,
    atr_entry: float,
    initial_sl: float,
    sl_mult: float = SL_MULT,
) -> float:
    """Stop Chandelier: max(trail, initial_sl). Non scende mai sotto initial_sl."""
    trail = max_high - sl_mult * atr_entry
    return max(trail, initial_sl)


def get_regime_config(vix: float) -> dict:
    """Restituisce max_positions e allow_entry in base al VIX."""
    if vix < 20:
        return {"allow_entry": True,  "max_positions": 3, "regime": "risk-on"}
    elif vix <= 25:
        return {"allow_entry": True,  "max_positions": 2, "regime": "cautious"}
    else:
        return {"allow_entry": False, "max_positions": 0, "regime": "risk-off"}
```

- [ ] **Step 4: Esegui — deve passare**
```bash
venv\Scripts\python -m pytest tests/test_position_sizing.py -v
```
Atteso: `9 passed`

- [ ] **Step 5: Commit**
```bash
git add position_sizing.py tests/test_position_sizing.py
git commit -m "feat: add position_sizing with chandelier stop and VIX regime"
```

---

## Task 3: claude_analyst_v3.py

**Files:**
- Crea: `claude_analyst_v3.py`

L'obiettivo è restituire `List[dict]` invece di una stringa, includere analyst consensus nel prompt, e rispettare `max_positions`.

- [ ] **Step 1: Implementa `claude_analyst_v3.py`**

```python
"""
claude_analyst_v3.py — LLM selector v3.
Estende v2: aggiunge analyst consensus nel prompt, restituisce List[dict] via JSON mode.
"""

import json
from groq import Groq
from config import GROQ_API_KEY

SYSTEM_PROMPT_V3 = """Sei un analista finanziario esperto. Ogni lunedi ricevi contesto macro, notizie, consensus analisti e snapshot tecnico.

REGOLE:
- Seleziona DA 0 A {max_positions} segnali BUY (su tutte le categorie).
- Setup tecnico solido + macro favorevole + notizie non negative = segnale valido.
- In Risk-Off (VIX>25): solo settori difensivi. In Risk-On: puoi includere tech/AI.
- Se notizie negative significative su un titolo: escludilo.
- RSI < 70, MACD favorevole, prezzo sopra almeno una SMA.
- Il consensus analisti (recommendation + upside%) è un fattore di rinforzo, non determinante.

Rispondi SOLO con un array JSON valido (nessun testo fuori dal JSON):
[
  {{
    "ticker": "AAPL",
    "category": "USA",
    "entry_price": 185.50,
    "sl": 176.50,
    "tp_note": "Chandelier exit gestisce l'uscita",
    "setup": "Breve motivazione (1 riga)",
    "analyst_upside_pct": 12.3
  }}
]
Se nessun segnale: []"""

USER_TEMPLATE_V3 = """Settimana del {date}

{macro_context}

{news_context}

=== ANALYST CONSENSUS ===
{analyst_json}

=== CANDIDATI TECNICI ({count} su {total}) ===
{snapshot_json}

Seleziona al massimo {max_positions} segnali BUY. Rispondi SOLO con JSON."""


def generate_signals(
    snapshot: dict,
    date: str,
    macro_context: str = "",
    news_context: str = "",
    analyst_data: dict = None,
    max_positions: int = 3,
) -> list:
    """
    Restituisce List[dict] con i segnali selezionati dall'LLM.
    Ogni dict ha: ticker, category, entry_price, sl, setup, analyst_upside_pct.
    """
    client = Groq(api_key=GROQ_API_KEY)
    count = sum(len(v) for v in snapshot.values())

    system = SYSTEM_PROMPT_V3.format(max_positions=max_positions)
    prompt = USER_TEMPLATE_V3.format(
        date=date,
        macro_context=macro_context or "(non disponibile)",
        news_context=news_context or "(non disponibile)",
        analyst_json=json.dumps(analyst_data or {}, indent=2, ensure_ascii=False),
        count=count,
        total=247,
        snapshot_json=json.dumps(snapshot, indent=2, ensure_ascii=False),
        max_positions=max_positions,
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=1000,
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()
    try:
        signals = json.loads(raw)
        if not isinstance(signals, list):
            return []
        return signals[:max_positions]
    except json.JSONDecodeError:
        # Fallback: tenta di estrarre JSON dall'output
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])[:max_positions]
            except Exception:
                pass
        return []
```

- [ ] **Step 2: Test manuale rapido (opzionale, richiede GROQ_API_KEY)**
```bash
venv\Scripts\python -c "
from claude_analyst_v3 import generate_signals
signals = generate_signals({}, '2026-05-30', max_positions=2)
print(type(signals), signals)
"
```
Atteso: `<class 'list'>` con 0-2 elementi.

- [ ] **Step 3: Commit**
```bash
git add claude_analyst_v3.py
git commit -m "feat: add claude_analyst_v3 returning structured JSON signals"
```

---

## Task 4: tracker_v3.py

**Files:**
- Crea: `tracker_v3.py`
- Crea: `tests/test_tracker_v3.py`

- [ ] **Step 1: Scrivi i test**

`tests/test_tracker_v3.py`:
```python
import json, os, tempfile
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime

# Helper: crea portfolio_v3.json temporaneo
def make_portfolio(open_positions):
    data = {"balance": 20000.0, "realized_pnl": 0.0,
            "open": open_positions, "closed": []}
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(data, tmp)
    tmp.close()
    return tmp.name

def test_chandelier_stop_updated_on_new_high():
    from tracker_v3 import update_chandelier_stop
    pos = {
        "ticker": "AAPL", "status": "active",
        "entry_price": 100.0, "atr_entry": 2.5,
        "initial_sl": 95.0, "max_high_since_entry": 105.0,
        "chandelier_stop": 100.0,
    }
    new_high = 110.0
    updated = update_chandelier_stop(pos, new_high)
    assert updated["max_high_since_entry"] == 110.0
    assert updated["chandelier_stop"] == 105.0  # 110 - 2*2.5

def test_chandelier_stop_not_lowered_on_lower_high():
    from tracker_v3 import update_chandelier_stop
    pos = {
        "ticker": "AAPL", "status": "active",
        "entry_price": 100.0, "atr_entry": 2.5,
        "initial_sl": 95.0, "max_high_since_entry": 110.0,
        "chandelier_stop": 105.0,
    }
    # nuovo high minore del precedente: stop non cambia
    updated = update_chandelier_stop(pos, 108.0)
    assert updated["max_high_since_entry"] == 110.0  # non aggiornato
    assert updated["chandelier_stop"] == 105.0        # invariato

def test_position_closed_when_low_hits_stop():
    from tracker_v3 import should_close
    pos = {"chandelier_stop": 105.0, "initial_sl": 95.0}
    assert should_close(h1_low=104.5, position=pos) is True

def test_position_not_closed_when_above_stop():
    from tracker_v3 import should_close
    pos = {"chandelier_stop": 105.0, "initial_sl": 95.0}
    assert should_close(h1_low=106.0, position=pos) is False
```

- [ ] **Step 2: Esegui — deve fallire**
```bash
venv\Scripts\python -m pytest tests/test_tracker_v3.py -v
```
Atteso: `ModuleNotFoundError: No module named 'tracker_v3'`

- [ ] **Step 3: Implementa `tracker_v3.py`**

```python
"""
tracker_v3.py — monitoring orario per v3 con Chandelier Exit.
Esegui ogni ora 9:00-22:00 lun-ven tramite Task Scheduler o daemon.
"""

import json
import os
from datetime import datetime
import yfinance as yf

from position_sizing import calculate_chandelier_stop
from notifier import send_telegram_message

PORTFOLIO_PATH = os.path.join(os.path.dirname(__file__), "portfolio_v3.json")
V3_PREFIX = "[V3]"


# --- Portfolio I/O ---

def load_portfolio() -> dict:
    if not os.path.exists(PORTFOLIO_PATH):
        return {"balance": 20000.0, "realized_pnl": 0.0, "open": [], "closed": []}
    with open(PORTFOLIO_PATH, "r") as f:
        return json.load(f)


def save_portfolio(portfolio: dict):
    with open(PORTFOLIO_PATH, "w") as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)


# --- Logica Chandelier (testabile in isolamento) ---

def update_chandelier_stop(position: dict, new_h1_high: float) -> dict:
    """Aggiorna max_high e chandelier_stop se il nuovo high è superiore."""
    if new_h1_high > position["max_high_since_entry"]:
        position["max_high_since_entry"] = new_h1_high
        position["chandelier_stop"] = calculate_chandelier_stop(
            max_high=new_h1_high,
            atr_entry=position["atr_entry"],
            initial_sl=position["initial_sl"],
        )
    return position


def should_close(h1_low: float, position: dict) -> bool:
    """True se il minimo H1 tocca o supera lo stop attivo."""
    active_stop = max(position["chandelier_stop"], position["initial_sl"])
    return h1_low <= active_stop


# --- Attivazione pending ---

def activate_pending(portfolio: dict) -> dict:
    """Converte posizioni pending in active usando il prezzo di apertura corrente."""
    for pos in portfolio["open"]:
        if pos["status"] != "pending":
            continue
        ticker = pos["ticker"]
        try:
            df = yf.download(ticker, period="1d", interval="1h", progress=False)
            if df.empty:
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            open_price = float(df["Open"].iloc[0])
            pos["entry_price"] = open_price
            pos["initial_sl"]  = round(open_price - 2.0 * pos["atr_entry"], 4)
            pos["max_high_since_entry"] = open_price
            pos["chandelier_stop"] = pos["initial_sl"]
            pos["status"] = "active"
            pos["entry_date"] = datetime.now().strftime("%Y-%m-%d")
            msg = (f"{V3_PREFIX} ✅ ENTRY {ticker} @ {open_price:.2f}\n"
                   f"SL: {pos['initial_sl']:.2f} | Size: {pos['size_eur']:.0f}€")
            send_telegram_message(msg)
        except Exception as e:
            print(f"[tracker_v3] WARN activate {ticker}: {e}")
    return portfolio


# --- Check chandelier + chiusura ---

def check_positions(portfolio: dict) -> dict:
    """Controlla ogni posizione attiva su H1. Chiude se chandelier stop colpito."""
    still_open = []
    for pos in portfolio["open"]:
        if pos["status"] != "active":
            still_open.append(pos)
            continue
        ticker = pos["ticker"]
        try:
            df = yf.download(ticker, period="7d", interval="1h", progress=False)
            if df.empty:
                still_open.append(pos)
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

            # Aggiorna chandelier con i massimi H1 dall'entry
            for _, row in df.iterrows():
                pos = update_chandelier_stop(pos, float(row["High"]))

            # Controlla se l'ultima barra ha toccato lo stop
            last_low = float(df["Low"].iloc[-1])
            last_close = float(df["Close"].iloc[-1])

            if should_close(last_low, pos):
                close_price = max(pos["chandelier_stop"], last_low)
                pnl_pct = (close_price - pos["entry_price"]) / pos["entry_price"] * 100
                pnl_eur = pnl_pct / 100 * pos["size_eur"]
                pos.update({
                    "status": "closed",
                    "close_price": round(close_price, 4),
                    "close_date": datetime.now().strftime("%Y-%m-%d"),
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_eur": round(pnl_eur, 2),
                })
                portfolio["balance"] += pnl_eur
                portfolio["realized_pnl"] += pnl_eur
                portfolio["closed"].append(pos)
                icon = "✅" if pnl_pct >= 0 else "❌"
                msg = (f"{V3_PREFIX} {icon} CLOSE {ticker} @ {close_price:.2f}\n"
                       f"P&L: {pnl_pct:+.2f}% ({pnl_eur:+.2f}€)\n"
                       f"Chandelier stop: {pos['chandelier_stop']:.2f}")
                send_telegram_message(msg)
            else:
                still_open.append(pos)
        except Exception as e:
            print(f"[tracker_v3] WARN check {ticker}: {e}")
            still_open.append(pos)

    portfolio["open"] = still_open
    return portfolio


# --- Entry point ---

def run():
    portfolio = load_portfolio()
    portfolio = activate_pending(portfolio)
    portfolio = check_positions(portfolio)
    save_portfolio(portfolio)


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Esegui i test — devono passare**
```bash
venv\Scripts\python -m pytest tests/test_tracker_v3.py -v
```
Atteso: `4 passed`

- [ ] **Step 5: Commit**
```bash
git add tracker_v3.py tests/test_tracker_v3.py
git commit -m "feat: add tracker_v3 with chandelier exit monitoring"
```

---

## Task 5: main_v3.py + analyst consensus fetcher

**Files:**
- Crea: `main_v3.py`

- [ ] **Step 1: Implementa `main_v3.py`**

```python
"""
main_v3.py — Entry point settimanale v3.
Esegui ogni lunedì mattina prima dell'apertura dei mercati.
"""

import json
import os
from datetime import datetime

import yfinance as yf

from analyzer import build_market_snapshot, get_top_signals
from macro_analyzer import get_macro_context
from news_fetcher import get_news_context
from claude_analyst_v3 import generate_signals
from earnings_filter import has_earnings_soon
from position_sizing import calculate_size, get_regime_config
from tracker_v3 import load_portfolio, save_portfolio, PORTFOLIO_PATH
from notifier import send_telegram_message

V3_PREFIX = "[V3]"
SL_MULT = 2.0


def fetch_analyst_consensus(tickers: list) -> dict:
    """
    Recupera recommendation e target price da yfinance per ogni ticker.
    Restituisce dict: {ticker: {recommendation, target_price, upside_pct}}
    """
    result = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            rec = info.get("recommendationKey", "")
            target = info.get("targetMeanPrice")
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if rec and target and price:
                upside = round((target - price) / price * 100, 1)
                result[ticker] = {
                    "recommendation": rec,
                    "target_price": round(target, 2),
                    "upside_pct": upside,
                }
        except Exception:
            pass
    return result


def init_portfolio_if_missing():
    if not os.path.exists(PORTFOLIO_PATH):
        data = {"balance": 20000.0, "realized_pnl": 0.0, "open": [], "closed": []}
        with open(PORTFOLIO_PATH, "w") as f:
            json.dump(data, f, indent=2)


def count_active(portfolio: dict) -> int:
    return sum(1 for p in portfolio["open"] if p["status"] in ("active", "pending"))


def run():
    init_portfolio_if_missing()
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Regime VIX
    macro = get_macro_context()
    vix = macro.get("vix_value", 20.0)
    regime = get_regime_config(vix)

    if not regime["allow_entry"]:
        msg = (f"{V3_PREFIX} ⚠️ Risk-Off (VIX={vix:.1f})\n"
               f"Nessuna nuova entry questa settimana.")
        send_telegram_message(msg)
        return

    # 2. Portfolio — controlla slot disponibili
    portfolio = load_portfolio()
    active = count_active(portfolio)
    slots = regime["max_positions"] - active
    if slots <= 0:
        send_telegram_message(f"{V3_PREFIX} Portfolio pieno ({active} posizioni). Nessuna nuova entry.")
        return

    # 3. Snapshot tecnico — top-10 candidati
    snapshot = build_market_snapshot()
    candidates = get_top_signals(snapshot, n=10, sl_mult=SL_MULT, rr=2.0)

    # 4. Earnings filter
    candidates = [c for c in candidates if not has_earnings_soon(c["ticker"], days=14)]
    if not candidates:
        send_telegram_message(f"{V3_PREFIX} Nessun candidato dopo earnings filter.")
        return

    # 5. Analyst consensus
    tickers = [c["ticker"] for c in candidates]
    analyst_data = fetch_analyst_consensus(tickers)

    # 6. Arricchisci snapshot con analyst data per l'LLM
    for cat in snapshot:
        for ticker in list(snapshot[cat].keys()):
            if ticker in analyst_data:
                snapshot[cat][ticker]["analyst"] = analyst_data[ticker]

    # Filtra snapshot ai soli candidati rimasti
    candidate_tickers = set(tickers)
    filtered_snapshot = {
        cat: {t: ind for t, ind in assets.items() if t in candidate_tickers}
        for cat, assets in snapshot.items()
    }

    # 7. News context
    news_ctx = get_news_context(filtered_snapshot)

    # 8. LLM selezione
    macro_str = macro.get("macro_summary", "")
    signals = generate_signals(
        snapshot=filtered_snapshot,
        date=today,
        macro_context=macro_str,
        news_context=news_ctx,
        analyst_data=analyst_data,
        max_positions=slots,
    )

    if not signals:
        send_telegram_message(f"{V3_PREFIX} Nessun setup BUY convincente questa settimana. (VIX={vix:.1f})")
        return

    # 9. Sizing dinamico + aggiunta al portfolio
    added = []
    for sig in signals[:slots]:
        ticker = sig.get("ticker", "")
        entry  = sig.get("entry_price", 0)
        atr    = next((c["atr"] for c in candidates if c["ticker"] == ticker), None)
        if not atr or not entry:
            continue

        size = calculate_size(entry_price=entry, atr_entry=atr)
        sl   = round(entry - SL_MULT * atr, 4)

        position = {
            "ticker":               ticker,
            "category":             sig.get("category", ""),
            "status":               "pending",
            "entry_price":          None,
            "size_eur":             size,
            "atr_entry":            round(atr, 4),
            "initial_sl":           sl,
            "max_high_since_entry": 0.0,
            "chandelier_stop":      sl,
            "setup":                sig.get("setup", ""),
            "entry_date":           None,
            "close_date":           None,
            "close_price":          None,
            "pnl_pct":              None,
            "pnl_eur":              None,
        }
        portfolio["open"].append(position)
        added.append(position)

    save_portfolio(portfolio)

    # 10. Telegram report
    lines = [f"{V3_PREFIX} 📊 Segnali settimana {today} (VIX={vix:.1f}, {regime['regime']})"]
    for p in added:
        upside = analyst_data.get(p["ticker"], {}).get("upside_pct", "n/a")
        lines.append(
            f"\n*{p['ticker']}* | Size: {p['size_eur']:.0f}€\n"
            f"SL: {p['initial_sl']:.2f} | Analyst upside: {upside}%\n"
            f"Setup: {p['setup']}"
        )
    lines.append(f"\nTotale posizioni attive: {active + len(added)}/{regime['max_positions']}")
    send_telegram_message("\n".join(lines))


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Test smoke manuale**
```bash
venv\Scripts\python -c "
import main_v3
print('Import OK')
"
```
Atteso: `Import OK` senza errori.

- [ ] **Step 3: Commit**
```bash
git add main_v3.py
git commit -m "feat: add main_v3 with regime filter, earnings filter, dynamic sizing, analyst consensus"
```

---

## Task 6: Scheduler + verifica end-to-end

**Files:**
- Verifica Task Scheduler Windows

- [ ] **Step 1: Crea `run_v3.bat`**
```bat
@echo off
cd /d "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot"
venv\Scripts\python main_v3.py
```
Salva come `run_v3.bat` nella cartella del progetto.

- [ ] **Step 2: Crea `run_tracker_v3.bat`**
```bat
@echo off
cd /d "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot"
venv\Scripts\python tracker_v3.py
```
Salva come `run_tracker_v3.bat`.

- [ ] **Step 3: Aggiungi al Task Scheduler Windows**

Per `main_v3.py` (lunedì ore 08:00):
```
schtasks /create /tn "StockBotV3_Weekly" /tr "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\run_v3.bat" /sc weekly /d MON /st 08:00
```

Per `tracker_v3.py` (ogni ora, lun-ven):
```
schtasks /create /tn "StockBotV3_Tracker" /tr "C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\run_tracker_v3.bat" /sc hourly /mo 1 /st 09:00
```

- [ ] **Step 4: Test run manuale di main_v3**
```bash
venv\Scripts\python main_v3.py
```
Controlla:
- Telegram riceve messaggio con prefisso `[V3]`
- `portfolio_v3.json` viene creato con posizioni pending
- Nessun errore in console

- [ ] **Step 5: Test run manuale di tracker_v3**
```bash
venv\Scripts\python tracker_v3.py
```
Controlla:
- Posizioni pending vengono attivate (se mercato aperto) o rimangono pending
- `portfolio_v3.json` aggiornato
- Nessun errore

- [ ] **Step 6: Esegui tutti i test**
```bash
venv\Scripts\python -m pytest tests/ -v
```
Atteso: tutti i test passano.

- [ ] **Step 7: Commit finale**
```bash
git add run_v3.bat run_tracker_v3.bat
git commit -m "feat: complete v3 with scheduler scripts and full test suite"
```

---

## Self-review checklist

- [x] **Spec coverage:** Chandelier Exit ✅ | Market regime ✅ | Sizing 40 EUR ✅ | Earnings filter ✅ | Analyst consensus ✅ | File separati ✅ | portfolio_v3.json ✅ | Telegram [V3] ✅
- [x] **Placeholders:** nessun TBD o TODO nel piano
- [x] **Type consistency:** `calculate_chandelier_stop` chiamata uguale in `position_sizing.py` e `tracker_v3.py` ✅ | `load_portfolio/save_portfolio` importate da `tracker_v3` in `main_v3` ✅
- [x] **Dipendenze:** `get_news_context` da `news_fetcher` — verificare firma esatta di `news_fetcher.py` prima di Task 5

> ⚠️ **Nota Task 5:** prima di implementare `main_v3.py`, verificare la firma di `get_news_context()` in `news_fetcher.py` (potrebbe prendere lista ticker o snapshot dict).
