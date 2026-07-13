"""Tracker orario del bot Serenity (hold-60). Gira ogni ora nelle ore di mercato.

Per ogni run:
1. carica portfolio_serenity.json
2. attiva le posizioni PENDING all'open reale del giorno (fissa SL e deadline +60gg)
3. per ogni posizione ATTIVA: scarica OHLC del giorno, aggiorna P&L non realizzato,
   verifica exit (SL colpito / scadenza 60gg / nuova stance bearish sul ticker)
4. chiude le posizioni uscite, aggiorna balance + realized, notifica Telegram
5. rigenera la pagina Obsidian
"""
import json
import os
import subprocess
import tempfile
from datetime import date

import pandas as pd

from serenity_data import load_tweets, build_fresh_events
from serenity_stance import load_cache
from serenity_signals import select_bearish_tickers
from serenity_live import activate, check_exit, close_position, mark_price
from notifier import send_telegram

HERE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(HERE, "portfolio_serenity.json")


def load_portfolio():
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_portfolio(pf):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(pf, f, ensure_ascii=False, indent=2)


def fetch_today_ohlc(ticker):
    """(open, high, low, close) dell'ultima seduta, o None."""
    import yfinance as yf
    df = yf.download(ticker, period="5d", interval="1d",
                     progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    r = df.iloc[-1]
    return (float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]))


def bearish_set():
    """Ticker diventati bearish (conv>=4) di recente, per gli exit."""
    tmp = os.path.join(tempfile.gettempdir(), "serenity_repo")
    path = os.path.join(tmp, "data", "aleabitoreddit_tweets.json")
    if not os.path.exists(path):
        return set()
    events = build_fresh_events(load_tweets(path))
    cache = load_cache()
    # finestra ampia: qualsiasi bearish dopo l'inizio dell'anno conta come warning
    return select_bearish_tickers(events, cache, since=date(2026, 1, 1))


def main():
    pf = load_portfolio()
    today = date.today()
    bears = bearish_set()
    notes = []

    for pos in list(pf["open"]):
        ohlc = fetch_today_ohlc(pos["ticker"])
        if ohlc is None:
            continue
        o, h, l, c = ohlc

        if pos["status"] == "pending":
            activate(pos, entry_price=o, entry_day=today)
            mark_price(pos, c)
            notes.append(f"▶️ `{pos['ticker']}` aperta @ {o:.2f} · SL {pos['initial_sl']:.2f} "
                         f"· scad. {pos['deadline']}")
            continue

        if pos["status"] != "active":
            continue

        mark_price(pos, c)
        res = check_exit(pos, low=l, close=c, open_=o, today=today,
                         bearish=pos["ticker"] in bears)
        if res:
            close_position(pos, res["exit_price"], today, res["reason"])
            pf["open"].remove(pos)
            pf["closed"].append(pos)
            pf["balance"] += pos["pnl_eur"]
            pf["realized_pnl"] = pf.get("realized_pnl", 0.0) + pos["pnl_eur"]
            icon = "✅" if pos["pnl_eur"] > 0 else "❌"
            notes.append(f"{icon} `{pos['ticker']}` chiusa ({res['reason']}) @ "
                         f"{res['exit_price']:.2f} · {pos['pnl_eur']:+.0f}€ ({pos['pnl_pct']:+.2f}%)")

    pf["unrealized_pnl"] = round(
        sum(p.get("unrealized_eur") or 0 for p in pf["open"] if p["status"] == "active"), 2)
    save_portfolio(pf)

    # pagina Obsidian
    try:
        from sync_serenity_obsidian import write_obsidian
        write_obsidian(pf)
    except Exception as e:
        print(f"sync obsidian saltato: {e}")

    if notes:
        send_telegram("*[SERENITY] Aggiornamento posizioni*\n\n" + "\n".join(notes))
    print(f"Tracker: {len(pf['open'])} aperte, {len(pf['closed'])} chiuse | "
          f"balance {pf['balance']:,.0f}€")


if __name__ == "__main__":
    main()
