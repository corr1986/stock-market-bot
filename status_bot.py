"""
Status Bot — processo persistente in ascolto su Telegram.
Risponde al comando /status con lo stato del portafoglio in tempo reale.
Avviato automaticamente all'accensione del PC via Task Scheduler.

Protezione anti-duplicato: un lock file impedisce che due istanze girino
contemporaneamente (causa 409 Conflict su getUpdates).
"""

import json
import os
import sys
from datetime import datetime
import yfinance as yf
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

LOCKFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "status_bot.lock")

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")


def load_portfolio() -> dict:
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"balance": 20000.0, "realized_pnl": 0.0, "open": [], "closed": []}


def get_current_price(ticker: str) -> float | None:
    try:
        df = yf.download(ticker, period="1d", interval="1h", progress=False, auto_adjust=True)
        if df.empty:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return round(float(df["Close"].iloc[-1]), 2)
    except Exception:
        return None


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        return

    portfolio = load_portfolio()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    msg = f"*Portfolio Status — {now}*\n\n"

    unrealized_total = 0.0

    if portfolio["open"]:
        msg += "*Posizioni aperte:*\n"
        for pos in portfolio["open"]:
            price = get_current_price(pos["ticker"])
            if price is not None:
                upnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
                upnl_eur = upnl_pct / 100 * pos["trade_eur"]
                unrealized_total += upnl_eur
                sign = "+" if upnl_pct >= 0 else ""
                icon = "🟢" if upnl_pct >= 0 else "🔴"
                msg += (
                    f"{icon} *{pos['ticker']}* {price:.2f}\n"
                    f"   Entry: {pos['entry_price']} | SL: {pos['sl']} | TP: {pos['tp']}\n"
                    f"   P&L: {sign}{upnl_pct:.2f}% ({sign}{upnl_eur:.0f}€)\n\n"
                )
            else:
                msg += f"⚪ *{pos['ticker']}* — prezzo non disponibile\n\n"
    else:
        msg += "*Nessuna posizione aperta.*\n\n"

    total_closed = [p for p in portfolio["closed"] if p["outcome"] in ("WIN", "LOSS", "TIMEOUT")]
    wins   = sum(1 for p in total_closed if p["outcome"] == "WIN")
    losses = sum(1 for p in total_closed if p["outcome"] == "LOSS")
    wr     = wins / len(total_closed) * 100 if total_closed else 0.0
    equity = portfolio["balance"] + unrealized_total

    msg += (
        f"*Riepilogo:*\n"
        f"Balance: {portfolio['balance']:,.0f}€\n"
        f"Non realizzato: {unrealized_total:+.0f}€\n"
        f"Equity totale: {equity:,.0f}€\n"
        f"P&L realizzato: {portfolio['realized_pnl']:+.0f}€\n"
        f"Trade chiusi: {wins}W / {losses}L (WR {wr:.1f}%)"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("status", status_command))
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Status bot avviato — in ascolto per /status")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    # --- Protezione singola istanza ---
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE) as f:
                existing_pid = int(f.read().strip())
            try:
                import psutil
                if psutil.pid_exists(existing_pid):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Status bot già in esecuzione (PID {existing_pid}). Uscita.")
                    sys.exit(0)
                else:
                    print(f"Lock file stale (PID {existing_pid} non esiste). Procedo.")
            except ImportError:
                # psutil non disponibile: se il lock file è recente (<1h) esci
                age_s = (datetime.now().timestamp()
                         - os.path.getmtime(LOCKFILE))
                if age_s < 3600:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Lock file recente ({age_s:.0f}s). Status bot probabilmente attivo. Uscita.")
                    sys.exit(0)
                else:
                    print(f"Lock file vecchio ({age_s/3600:.1f}h). Procedo.")
        except (ValueError, OSError):
            pass  # lock file corrotto — procedi

    # Scrivi il lock
    with open(LOCKFILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        main()
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CRASH: {e}")
    finally:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
