"""
tracker_v3.py — monitoring orario con Chandelier Exit.
Eseguire ogni ora 9:00-22:00 lun-ven tramite Task Scheduler.
"""

import json
import os
from datetime import datetime
import yfinance as yf

from position_sizing import calculate_chandelier_stop
from notifier import send_telegram as send_telegram_message

PORTFOLIO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_v3.json")
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


# --- Logica Chandelier (funzioni pure, testabili) ---

def update_chandelier_stop(position: dict, new_h1_high: float) -> dict:
    """Aggiorna max_high e chandelier_stop solo se il nuovo high è superiore."""
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
            pos["entry_price"]          = open_price
            pos["initial_sl"]           = round(open_price - 2.0 * pos["atr_entry"], 4)
            pos["max_high_since_entry"] = open_price
            pos["chandelier_stop"]      = pos["initial_sl"]
            pos["status"]               = "active"
            pos["entry_date"]           = datetime.now().strftime("%Y-%m-%d")
            msg = (f"{V3_PREFIX} ✅ ENTRY {ticker} @ {open_price:.2f}\n"
                   f"SL: {pos['initial_sl']:.2f} | Size: {pos['size_eur']:.0f}€")
            send_telegram_message(msg)
        except Exception as e:
            print(f"[tracker_v3] WARN activate {ticker}: {e}")
    return portfolio


# --- Check chandelier + chiusura ---

def check_positions(portfolio: dict) -> dict:
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

            for _, row in df.iterrows():
                pos = update_chandelier_stop(pos, float(row["High"]))

            last_low   = float(df["Low"].iloc[-1])
            last_close = float(df["Close"].iloc[-1])

            if should_close(last_low, pos):
                close_price = max(pos["chandelier_stop"], last_low)
                pnl_pct = (close_price - pos["entry_price"]) / pos["entry_price"] * 100
                pnl_eur = pnl_pct / 100 * pos["size_eur"]
                pos.update({
                    "status":      "closed",
                    "close_price": round(close_price, 4),
                    "close_date":  datetime.now().strftime("%Y-%m-%d"),
                    "pnl_pct":     round(pnl_pct, 2),
                    "pnl_eur":     round(pnl_eur, 2),
                })
                portfolio["balance"]      += pnl_eur
                portfolio["realized_pnl"] += pnl_eur
                portfolio["closed"].append(pos)
                icon = "✅" if pnl_pct >= 0 else "❌"
                msg = (f"{V3_PREFIX} {icon} CLOSE {ticker} @ {close_price:.2f}\n"
                       f"P&L: {pnl_pct:+.2f}% ({pnl_eur:+.2f}€)\n"
                       f"Stop: {pos['chandelier_stop']:.2f}")
                send_telegram_message(msg)
            else:
                still_open.append(pos)
        except Exception as e:
            print(f"[tracker_v3] WARN check {ticker}: {e}")
            still_open.append(pos)

    portfolio["open"] = still_open
    return portfolio


def run():
    portfolio = load_portfolio()
    portfolio = activate_pending(portfolio)
    portfolio = check_positions(portfolio)
    save_portfolio(portfolio)


if __name__ == "__main__":
    run()
