"""Backtest FASE 1 strategia Serenity fresh-ticker.

Regole (spec docs/superpowers/specs/2026-07-08-serenity-signals-design.md):
- evento freshness + stance bullish conviction >= 4 -> BUY all'open del giorno dopo
- SL iniziale 2xATR(14), trailing Chandelier (riuso position_sizing), no TP
- rischio 40 EUR/trade, max 3 posizioni, VIX>30 blocca entry (get_regime_config)
Semplificazioni FASE 1 (documentate): niente earnings filter storico,
niente SELL anticipato su stance bearish, niente limite dinamico posizioni
nel regime cautious.
"""
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
        # lo stop non scatta sul Low del giorno di entry (SL piazzato dopo l'apertura)
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
