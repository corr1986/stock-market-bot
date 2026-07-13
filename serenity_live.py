"""Logica core del bot live Serenity — modello hold-60 (vincente nel backtest).

Regole (report docs/superpowers/specs/2026-07-13-serenity-backtest-report.md):
- Entry: segnale bullish fresco conv>=4 -> compra all'open del giorno dopo, azioni intere (min 1)
- SL iniziale: entry - 2*ATR(14), fisso (no trailing)
- Exit: scadenza 60 giorni di calendario, OPPURE SL colpito, OPPURE nuova stance bearish
- Capitale 50.000 EUR, size 500 EUR/trade (~1% del capitale, come nel backtest validato)

Funzioni pure e testabili; l'I/O (prezzi, Groq, file) sta negli orchestratori
serenity_daily.py / serenity_tracker.py.
"""
from datetime import date, datetime, timedelta

CAPITAL_START = 50_000.0
SIZE_EUR = 500.0
SL_ATR_MULT = 2.0
HOLD_DAYS = 60


def plan_entry(ticker, entry_ref, atr, signal_date):
    """Crea una posizione 'pending' da un segnale. None se dati non validi.

    entry_ref: prezzo di riferimento al momento del segnale (per SL e sizing).
    Le azioni sono intere (minimo 1); size effettiva = shares * entry_ref.
    deadline resta None: viene fissato all'attivazione (entry reale all'open).
    """
    if entry_ref <= 0 or atr <= 0:
        return None
    shares = max(1, int(SIZE_EUR // entry_ref))
    return {
        "ticker": ticker,
        "status": "pending",
        "signal_date": signal_date.isoformat(),
        "entry_ref": entry_ref,
        "atr_entry": atr,
        "shares": shares,
        "size_eur": shares * entry_ref,
        "initial_sl": entry_ref - SL_ATR_MULT * atr,
        "entry_price": None,
        "entry_date": None,
        "deadline": None,
        "close_date": None,
        "close_price": None,
        "pnl_pct": None,
        "pnl_eur": None,
        "current_price": None,
        "unrealized_pct": None,
        "unrealized_eur": None,
    }


def activate(pos, entry_price, entry_day):
    """Passa una pending ad 'active' al prezzo di apertura reale.

    Ricalcola SL sull'entry reale e fissa la deadline a +HOLD_DAYS giorni.
    """
    atr = pos["atr_entry"]
    pos["status"] = "active"
    pos["entry_price"] = entry_price
    pos["entry_date"] = entry_day.isoformat()
    pos["initial_sl"] = entry_price - SL_ATR_MULT * atr
    pos["deadline"] = (entry_day + timedelta(days=HOLD_DAYS)).isoformat()
    return pos


def check_exit(pos, low, close, open_, today, bearish):
    """Decide se chiudere una posizione active. Ritorna dict o None.

    Priorita' (conservativa): SL prima di deadline/bearish.
    - gap: open sotto SL -> exit all'open; altrimenti se low<=SL -> exit allo SL
    - deadline: today >= deadline -> exit al close
    - bearish: nuova stance bearish sul ticker -> exit al close
    """
    sl = pos["initial_sl"]
    if open_ < sl:
        return {"reason": "stop_loss", "exit_price": open_}
    if low <= sl:
        return {"reason": "stop_loss", "exit_price": sl}

    deadline = date.fromisoformat(pos["deadline"])
    if today >= deadline:
        return {"reason": "deadline", "exit_price": close}
    if bearish:
        return {"reason": "bearish", "exit_price": close}
    return None


def close_position(pos, exit_price, exit_day, reason):
    """Applica la chiusura: calcola P&L per azione e marca lo stato."""
    entry = pos["entry_price"]
    pnl_eur = pos["shares"] * (exit_price - entry)
    pos["status"] = "closed"
    pos["close_date"] = exit_day.isoformat()
    pos["close_price"] = round(exit_price, 4)
    pos["close_reason"] = reason
    pos["pnl_eur"] = round(pnl_eur, 2)
    pos["pnl_pct"] = round((exit_price - entry) / entry * 100, 2)
    return pos


def mark_price(pos, price):
    """Aggiorna prezzo corrente e P&L non realizzato di una posizione active."""
    entry = pos["entry_price"]
    pos["current_price"] = round(price, 4)
    pos["unrealized_pct"] = round((price - entry) / entry * 100, 2)
    pos["unrealized_eur"] = round(pos["shares"] * (price - entry), 2)
    return pos


def invested_capital(portfolio):
    """Capitale impegnato nelle posizioni aperte (pending + active)."""
    return sum(p["size_eur"] for p in portfolio.get("open", []))
