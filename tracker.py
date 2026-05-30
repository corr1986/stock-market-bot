"""
Paper Trading Tracker — gira ogni ora 9:00-22:00 lun-ven.
- Attiva posizioni pending al prezzo di apertura del mercato
- Verifica SL/TP su barre H1 per le posizioni attive
- Aggiorna portfolio.json e Portfolio Status.md
- Manda Telegram solo quando una posizione si chiude
"""

import json
import os
import sys
from datetime import datetime, date, timezone
import yfinance as yf
from notifier import send_telegram

PORTFOLIO_FILE  = os.path.join(os.path.dirname(__file__), "portfolio.json")
OBSIDIAN_STATUS = os.path.join(os.path.dirname(__file__), "..", "Portfolio Status.md")
SAFETY_CAP_BARS = 365 * 7
# Bloomberg V2 config — deve corrispondere a backtest_mixed.py / analyzer.py
SL_MULT = 2.0
RR      = 2.0


def load_portfolio() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        print("portfolio.json non trovato. Nessuna posizione da tracciare.")
        sys.exit(0)
    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_portfolio(p: dict):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Attivazione posizioni pending
# ---------------------------------------------------------------------------

def is_market_open(ticker: str) -> bool:
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    h = now.hour + now.minute / 60
    if "." in ticker:
        return 7.0 <= h < 16.5    # Europa: 9:00-18:30 IT (UTC+2)
    else:
        return 13.5 <= h < 20.0   # USA: 15:30-22:00 IT


def get_day_open(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).info
        val = info.get("regularMarketOpen") or info.get("open")
        if val is None:
            return None
        return round(float(val), 4)
    except Exception:
        return None


def activate_pending(portfolio: dict) -> int:
    activated = 0
    for pos in portfolio["open"]:
        if pos.get("status") != "pending":
            continue
        if not is_market_open(pos["ticker"]):
            print(f"  {pos['ticker']}: in attesa apertura mercato")
            continue
        open_price = get_day_open(pos["ticker"])
        if open_price is None:
            print(f"  {pos['ticker']}: prezzo apertura non disponibile")
            continue
        atr = pos["atr"]
        pos["entry_date"]  = date.today().strftime("%Y-%m-%d")
        pos["entry_price"] = open_price
        pos["sl"]          = round(open_price - SL_MULT * atr, 4)
        pos["tp"]          = round(open_price + RR * SL_MULT * atr, 4)
        pos["status"]      = "active"
        activated += 1
        print(f"  {pos['ticker']} ATTIVATA -> entry={open_price} SL={pos['sl']} TP={pos['tp']}")
    return activated


# ---------------------------------------------------------------------------
# Verifica SL/TP posizioni attive
# ---------------------------------------------------------------------------

def check_position(pos: dict) -> tuple:
    ticker      = pos["ticker"]
    entry_date  = pos["entry_date"]
    entry_price = pos["entry_price"]
    sl          = pos["sl"]
    tp          = pos["tp"]

    try:
        df = yf.download(ticker, period="7d", interval="1h",
                         progress=False, auto_adjust=True)
    except Exception as e:
        print(f"  Errore download {ticker}: {e}")
        return "OPEN", entry_price, None, 0

    if df.empty:
        return "OPEN", entry_price, None, 0

    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    entry_ts = datetime.strptime(entry_date, "%Y-%m-%d")
    df.index = df.index.tz_localize(None) if df.index.tzinfo is not None else df.index
    df = df[df.index > entry_ts]

    if df.empty:
        return "OPEN", entry_price, None, 0

    for i, (bar_date, row) in enumerate(df.iterrows()):
        if i >= SAFETY_CAP_BARS:
            close = float(df["Close"].iloc[i - 1])
            return "TIMEOUT", close, str(bar_date.date()), i
        low  = float(row["Low"])
        high = float(row["High"])
        if low <= sl:
            return "LOSS", sl, str(bar_date.date()), i + 1
        if high >= tp:
            return "WIN", tp, str(bar_date.date()), i + 1

    last_close = float(df["Close"].iloc[-1])
    last_date  = str(df.index[-1].date())
    return "OPEN", last_close, last_date, len(df)


# ---------------------------------------------------------------------------
# Telegram e Obsidian
# ---------------------------------------------------------------------------

def build_telegram_message(closed_today: list, portfolio: dict) -> str:
    today = date.today().strftime("%d/%m/%Y")
    msg = f"*Portfolio Tracker — {today}*\n\n"

    for t in closed_today:
        icon = "✅" if t["outcome"] == "WIN" else ("⏱" if t["outcome"] == "TIMEOUT" else "❌")
        sign = "+" if t["pnl_eur"] >= 0 else ""
        msg += (
            f"{icon} *{t['ticker']}* — {t['outcome']}\n"
            f"Entry: {t['entry_price']} -> Exit: {t['exit_price']} ({t['exit_date']})\n"
            f"P&L: {t['pnl_pct']:+.2f}% | {sign}{t['pnl_eur']:.0f}EUR "
            f"({t['days_held']} giorni)\n\n"
        )

    total_closed = [p for p in portfolio["closed"] if p["outcome"] in ("WIN", "LOSS", "TIMEOUT")]
    wins   = sum(1 for p in total_closed if p["outcome"] == "WIN")
    losses = sum(1 for p in total_closed if p["outcome"] == "LOSS")
    wr     = wins / len(total_closed) * 100 if total_closed else 0.0

    active = [p for p in portfolio["open"] if p.get("status") == "active"]
    unrealized = 0.0
    for pos in active:
        _, cur_price, _, _ = check_position(pos)
        if cur_price and pos["entry_price"]:
            unrealized += (cur_price - pos["entry_price"]) / pos["entry_price"] * 100 / 100 * pos["trade_eur"]

    pending_n = sum(1 for p in portfolio["open"] if p.get("status") == "pending")

    msg += (
        f"*Portafoglio*\n"
        f"Balance: {portfolio['balance']:,.0f}EUR\n"
        f"P&L realizzato: {portfolio['realized_pnl']:+.0f}EUR\n"
        f"P&L non realizzato: {unrealized:+.0f}EUR\n"
        f"Trade chiusi: {wins}W / {losses}L (WR {wr:.1f}%)\n"
        f"Posizioni attive: {len(active)} | In attesa: {pending_n}"
    )
    return msg


def write_obsidian_status(portfolio: dict, open_status: list, pending: list):
    today = datetime.now().strftime("%d/%m/%Y %H:%M")
    total_closed = [p for p in portfolio["closed"] if p["outcome"] in ("WIN", "LOSS", "TIMEOUT")]
    wins   = sum(1 for p in total_closed if p["outcome"] == "WIN")
    losses = sum(1 for p in total_closed if p["outcome"] == "LOSS")
    wr     = wins / len(total_closed) * 100 if total_closed else 0.0

    unrealized_eur = sum(s["unrealized_eur"] for s in open_status)
    equity = portfolio["balance"] + unrealized_eur

    lines = [
        "# Portfolio Status",
        f"*Aggiornato: {today}*",
        "",
        "## Riepilogo",
        "| Voce | Valore |",
        "|---|---|",
        "| Capitale iniziale | 20.000€ |",
        f"| Balance (cash) | {portfolio['balance']:,.0f}€ |",
        f"| P&L non realizzato | {unrealized_eur:+.0f}€ |",
        f"| **Equity totale** | **{equity:,.0f}€** |",
        f"| P&L realizzato | {portfolio['realized_pnl']:+.0f}€ |",
        f"| Trade chiusi | {len(total_closed)} ({wins}W / {losses}L) |",
        f"| Win Rate | {wr:.1f}% |",
        "",
        "## Posizioni attive",
    ]

    if open_status:
        lines += [
            "| Data apertura | Ticker | Entry | Prezzo attuale | P&L % | P&L € | SL | SL % | SL € | TP | TP % | TP € |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for s in open_status:
            sign = "+" if s["unrealized_pct"] >= 0 else ""
            lines.append(
                f"| {s['entry_date']} | {s['ticker']} | {s['entry_price']} | {s['current_price']:.2f} "
                f"| {sign}{s['unrealized_pct']:.2f}% | {sign}{s['unrealized_eur']:.0f}€ "
                f"| {s['sl']} | {s['sl_pct']:+.2f}% | {s['sl_eur']:+.0f}€ "
                f"| {s['tp']} | {s['tp_pct']:+.2f}% | {s['tp_eur']:+.0f}€ |"
            )
    else:
        lines.append("*Nessuna posizione attiva.*")

    if pending:
        lines += ["", "## In attesa di apertura mercato"]
        lines += ["| Ticker | Categoria | ATR |", "|---|---|---|"]
        for p in pending:
            lines.append(f"| {p['ticker']} | {p['category']} | {p['atr']} |")

    lines += ["", "## Storico trade chiusi"]
    if total_closed:
        lines += [
            "| Data entrata | Data uscita | Ticker | Esito | P&L % | P&L € | Giorni |",
            "|---|---|---|---|---|---|---|",
        ]
        for p in reversed(total_closed):
            icon = "✅" if p["outcome"] == "WIN" else ("⏱" if p["outcome"] == "TIMEOUT" else "❌")
            lines.append(
                f"| {p['entry_date']} | {p.get('exit_date', '—')} | {p['ticker']} "
                f"| {icon} {p['outcome']} | {p['pnl_pct']:+.2f}% | {p['pnl_eur']:+.0f}€ "
                f"| {p.get('days_held', '—')} |"
            )
    else:
        lines.append("*Nessun trade ancora chiuso.*")

    with open(OBSIDIAN_STATUS, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"[{today_str}] Paper Trading Tracker avviato")

    portfolio = load_portfolio()

    if not portfolio["open"]:
        print("Nessuna posizione aperta.")
        write_obsidian_status(portfolio, [], [])
        return

    # 1. Attiva posizioni pending al prezzo di apertura
    print("Verifica posizioni pending...")
    activated = activate_pending(portfolio)
    if activated:
        save_portfolio(portfolio)

    # 2. Controlla SL/TP solo per posizioni attive
    active  = [p for p in portfolio["open"] if p.get("status") == "active"]
    pending = [p for p in portfolio["open"] if p.get("status") == "pending"]

    print(f"Posizioni attive: {len(active)} | In attesa: {len(pending)}")

    closed_today = []
    still_open   = []
    open_status  = []

    for pos in active:
        ticker = pos["ticker"]
        print(f"  Controllo {ticker}...", end=" ")
        outcome, exit_price, exit_date, days_held = check_position(pos)

        if outcome in ("WIN", "LOSS", "TIMEOUT"):
            pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
            pnl_eur = pnl_pct / 100 * pos["trade_eur"]
            closed_pos = {
                **pos,
                "exit_date":  exit_date,
                "exit_price": round(exit_price, 4),
                "outcome":    outcome,
                "pnl_pct":   round(pnl_pct, 2),
                "pnl_eur":   round(pnl_eur, 2),
                "days_held": days_held,
            }
            portfolio["closed"].append(closed_pos)
            portfolio["balance"]      += pnl_eur
            portfolio["realized_pnl"] += pnl_eur
            closed_today.append(closed_pos)
            print(f"{outcome} | P&L {pnl_pct:+.2f}% ({pnl_eur:+.0f}€)")
        else:
            unrealized_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
            unrealized_eur = unrealized_pct / 100 * pos["trade_eur"]
            tp_pct = (pos["tp"] - pos["entry_price"]) / pos["entry_price"] * 100
            tp_eur = tp_pct / 100 * pos["trade_eur"]
            sl_pct = (pos["sl"] - pos["entry_price"]) / pos["entry_price"] * 100
            sl_eur = sl_pct / 100 * pos["trade_eur"]
            print(f"aperta | {exit_price:.2f} ({unrealized_pct:+.2f}%)")
            still_open.append(pos)
            open_status.append({
                "ticker":         pos["ticker"],
                "entry_date":     pos["entry_date"],
                "entry_price":    pos["entry_price"],
                "current_price":  round(exit_price, 2),
                "unrealized_pct": round(unrealized_pct, 2),
                "unrealized_eur": round(unrealized_eur, 2),
                "sl":             pos["sl"],
                "sl_pct":         round(sl_pct, 2),
                "sl_eur":         round(sl_eur, 2),
                "tp":             pos["tp"],
                "tp_pct":         round(tp_pct, 2),
                "tp_eur":         round(tp_eur, 2),
            })

    portfolio["open"] = still_open + pending
    save_portfolio(portfolio)
    write_obsidian_status(portfolio, open_status, pending)
    print("Portfolio Status.md aggiornato.")

    if closed_today:
        print("Invio notifica Telegram...")
        ok = send_telegram(build_telegram_message(closed_today, portfolio))
        print("Notifica inviata." if ok else "Errore invio Telegram.")
    else:
        print("Nessuna posizione chiusa oggi.")


if __name__ == "__main__":
    run()
