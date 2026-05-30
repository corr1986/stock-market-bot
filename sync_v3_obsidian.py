"""
sync_v3_obsidian.py
-------------------
Legge portfolio_v3.json (aggiornato da GitHub Actions) e scrive
Portfolio Status V3.md nel vault Obsidian.
Lanciato ogni mattina da Task Scheduler dopo git pull.
"""

import json
import os
import subprocess
from datetime import date

PORTFOLIO_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_v3.json")
OBSIDIAN_STATUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Portfolio Status V3.md")


def git_pull():
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True, text=True, timeout=30
        )
        print(result.stdout.strip() or "git pull ok")
    except Exception as e:
        print(f"git pull fallito: {e}")


def load_portfolio() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        return {"balance": 20000.0, "realized_pnl": 0.0, "open": [], "closed": []}
    with open(PORTFOLIO_FILE, "r") as f:
        return json.load(f)


def write_obsidian(portfolio: dict):
    today = date.today().strftime("%Y-%m-%d")
    open_pos  = [p for p in portfolio["open"] if p["status"] == "active"]
    pending   = [p for p in portfolio["open"] if p["status"] == "pending"]
    closed    = portfolio.get("closed", [])

    wins   = sum(1 for p in closed if (p.get("pnl_pct") or 0) > 0)
    losses = sum(1 for p in closed if (p.get("pnl_pct") or 0) <= 0)
    wr     = (wins / len(closed) * 100) if closed else 0.0
    equity = portfolio["balance"]

    lines = [
        "# Portfolio Status V3",
        f"*Aggiornato: {today} — paper trading parallelo a v1*",
        "",
        "## Riepilogo",
        "| Voce | Valore |",
        "|---|---|",
        "| Capitale iniziale | 20.000€ |",
        f"| Balance (cash) | {portfolio['balance']:,.0f}€ |",
        f"| **Equity totale** | **{equity:,.0f}€** |",
        f"| P&L realizzato | {portfolio['realized_pnl']:+.0f}€ |",
        f"| Trade chiusi | {len(closed)} ({wins}W / {losses}L) |",
        f"| Win Rate | {wr:.1f}% |",
        "",
        "## Posizioni attive",
    ]

    if open_pos:
        lines += [
            "| Data apertura | Ticker | Entry | Size | SL | Chandelier Stop |",
            "|---|---|---|---|---|---|",
        ]
        for p in open_pos:
            lines.append(
                f"| {p.get('entry_date', '—')} | {p['ticker']} "
                f"| {p.get('entry_price', '—')} | {p['size_eur']:.0f}€ "
                f"| {p['initial_sl']:.2f} | {p['chandelier_stop']:.2f} |"
            )
    else:
        lines.append("*Nessuna posizione attiva.*")

    if pending:
        lines += ["", "## In attesa di apertura mercato"]
        lines += ["| Ticker | Categoria | Size | SL previsto |", "|---|---|---|---|"]
        for p in pending:
            lines.append(f"| {p['ticker']} | {p['category']} | {p['size_eur']:.0f}€ | {p['initial_sl']:.2f} |")

    lines += ["", "## Storico trade chiusi"]
    if closed:
        lines += [
            "| Data entrata | Data uscita | Ticker | P&L % | P&L € |",
            "|---|---|---|---|---|",
        ]
        for p in reversed(closed):
            icon = "✅" if (p.get("pnl_pct") or 0) > 0 else "❌"
            lines.append(
                f"| {p.get('entry_date', '—')} | {p.get('close_date', '—')} "
                f"| {p['ticker']} | {icon} {p.get('pnl_pct', 0):+.2f}% "
                f"| {p.get('pnl_eur', 0):+.0f}€ |"
            )
    else:
        lines.append("*Nessun trade ancora chiuso.*")

    lines += [
        "",
        "---",
        "*V3 Features: Chandelier Exit · VIX Regime Filter · Dynamic Sizing (40€ risk) · Earnings Filter*",
        f"*[Vedi portfolio_v3.json su GitHub](https://github.com/corr1986/stock-market-bot/blob/main/portfolio_v3.json)*",
    ]

    with open(OBSIDIAN_STATUS, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Portfolio Status V3.md aggiornato ({today})")


if __name__ == "__main__":
    print("Sync v3 Obsidian...")
    git_pull()
    portfolio = load_portfolio()
    write_obsidian(portfolio)
