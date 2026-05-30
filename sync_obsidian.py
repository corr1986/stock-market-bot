"""
sync_obsidian.py
----------------
git pull + rigenera Portfolio Status.md (v1) e Portfolio Status V3.md (v3)
nel vault Obsidian a partire dai JSON aggiornati da GitHub Actions.

Lanciato a ogni avvio del PC dal Task Scheduler.
"""

import json
import os
import subprocess
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.path.join(BASE_DIR, "..")

PORTFOLIO_V1   = os.path.join(BASE_DIR, "portfolio.json")
PORTFOLIO_V3   = os.path.join(BASE_DIR, "portfolio_v3.json")
STATUS_V1_PATH = os.path.join(VAULT_DIR, "Portfolio", "Portfolio V1.md")
STATUS_V3_PATH = os.path.join(VAULT_DIR, "Portfolio", "Portfolio V3.md")


# ---------------------------------------------------------------------------
# Git pull
# ---------------------------------------------------------------------------

def git_pull():
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=BASE_DIR,
            capture_output=True, text=True, timeout=30
        )
        print(result.stdout.strip() or "git pull: già aggiornato")
        if result.returncode != 0:
            print(f"WARN git pull: {result.stderr.strip()}")
    except Exception as e:
        print(f"git pull fallito: {e}")


# ---------------------------------------------------------------------------
# Portfolio helpers
# ---------------------------------------------------------------------------

def load_json(path: str, default: dict) -> dict:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# V1 — Portfolio Status.md
# ---------------------------------------------------------------------------

def write_status_v1(portfolio: dict):
    today = date.today().strftime("%d/%m/%Y %H:%M")
    closed     = [p for p in portfolio.get("closed", []) if p.get("outcome") in ("WIN", "LOSS", "TIMEOUT")]
    open_pos   = [p for p in portfolio.get("open",   []) if p.get("status") == "active"]
    pending    = [p for p in portfolio.get("open",   []) if p.get("status") == "pending"]
    wins       = sum(1 for p in closed if p.get("outcome") == "WIN")
    losses     = sum(1 for p in closed if p.get("outcome") == "LOSS")
    wr         = wins / len(closed) * 100 if closed else 0.0
    unrealized = sum(p.get("unrealized_eur", 0) for p in open_pos)
    equity     = portfolio["balance"] + unrealized

    lines = [
        "# Portfolio Status",
        f"*Aggiornato: {today}*",
        "",
        "## Riepilogo",
        "| Voce | Valore |",
        "|---|---|",
        "| Capitale iniziale | 20.000€ |",
        f"| Balance (cash) | {portfolio['balance']:,.0f}€ |",
        f"| P&L non realizzato | {unrealized:+.0f}€ |",
        f"| **Equity totale** | **{equity:,.0f}€** |",
        f"| P&L realizzato | {portfolio['realized_pnl']:+.0f}€ |",
        f"| Trade chiusi | {len(closed)} ({wins}W / {losses}L) |",
        f"| Win Rate | {wr:.1f}% |",
        "",
        "## Posizioni attive",
    ]

    if open_pos:
        lines += [
            "| Data apertura | Ticker | Entry | SL | TP |",
            "|---|---|---|---|---|",
        ]
        for p in open_pos:
            lines.append(
                f"| {p.get('entry_date','—')} | {p['ticker']} "
                f"| {p.get('entry_price','—')} | {p.get('sl','—')} | {p.get('tp','—')} |"
            )
    else:
        lines.append("*Nessuna posizione attiva.*")

    if pending:
        lines += ["", "## In attesa di apertura mercato",
                  "| Ticker | Categoria | ATR |", "|---|---|---|"]
        for p in pending:
            lines.append(f"| {p['ticker']} | {p.get('category','—')} | {p.get('atr','—')} |")

    lines += ["", "## Storico trade chiusi"]
    if closed:
        lines += [
            "| Data entrata | Data uscita | Ticker | Esito | P&L % | P&L € |",
            "|---|---|---|---|---|---|",
        ]
        for p in reversed(closed):
            icon = "✅" if p.get("outcome") == "WIN" else ("⏱" if p.get("outcome") == "TIMEOUT" else "❌")
            lines.append(
                f"| {p.get('entry_date','—')} | {p.get('exit_date','—')} "
                f"| {p['ticker']} | {icon} {p.get('outcome','')} "
                f"| {p.get('pnl_pct',0):+.2f}% | {p.get('pnl_eur',0):+.0f}€ |"
            )
    else:
        lines.append("*Nessun trade ancora chiuso.*")

    lines += ["", "---",
              f"*[Vedi portfolio.json su GitHub](https://github.com/corr1986/stock-market-bot/blob/main/portfolio.json)*"]

    with open(STATUS_V1_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Portfolio Status.md aggiornato (v1)")


# ---------------------------------------------------------------------------
# V3 — Portfolio Status V3.md
# ---------------------------------------------------------------------------

def write_status_v3(portfolio: dict):
    today  = date.today().strftime("%d/%m/%Y %H:%M")
    closed = portfolio.get("closed", [])
    open_pos = [p for p in portfolio.get("open", []) if p.get("status") == "active"]
    pending  = [p for p in portfolio.get("open", []) if p.get("status") == "pending"]
    wins   = sum(1 for p in closed if (p.get("pnl_pct") or 0) > 0)
    losses = sum(1 for p in closed if (p.get("pnl_pct") or 0) <= 0)
    wr     = wins / len(closed) * 100 if closed else 0.0
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
                f"| {p.get('entry_date','—')} | {p['ticker']} "
                f"| {p.get('entry_price','—')} | {p.get('size_eur',0):.0f}€ "
                f"| {p.get('initial_sl','—')} | {p.get('chandelier_stop','—')} |"
            )
    else:
        lines.append("*Nessuna posizione attiva.*")

    if pending:
        lines += ["", "## In attesa di apertura mercato",
                  "| Ticker | Categoria | Size | SL previsto |", "|---|---|---|---|"]
        for p in pending:
            lines.append(
                f"| {p['ticker']} | {p.get('category','—')} "
                f"| {p.get('size_eur',0):.0f}€ | {p.get('initial_sl','—')} |"
            )

    lines += ["", "## Storico trade chiusi"]
    if closed:
        lines += [
            "| Data entrata | Data uscita | Ticker | P&L % | P&L € |",
            "|---|---|---|---|---|",
        ]
        for p in reversed(closed):
            icon = "✅" if (p.get("pnl_pct") or 0) > 0 else "❌"
            lines.append(
                f"| {p.get('entry_date','—')} | {p.get('close_date','—')} "
                f"| {p['ticker']} | {icon} {p.get('pnl_pct',0):+.2f}% "
                f"| {p.get('pnl_eur',0):+.0f}€ |"
            )
    else:
        lines.append("*Nessun trade ancora chiuso.*")

    lines += [
        "", "---",
        "*V3 Features: Chandelier Exit · VIX Regime Filter · Dynamic Sizing (40€ risk) · Earnings Filter*",
        f"*[Vedi portfolio_v3.json su GitHub](https://github.com/corr1986/stock-market-bot/blob/main/portfolio_v3.json)*",
    ]

    with open(STATUS_V3_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("Portfolio Status V3.md aggiornato (v3)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Sync Obsidian (v1 + v3)...")
    git_pull()

    default = {"balance": 20000.0, "realized_pnl": 0.0, "open": [], "closed": []}
    write_status_v1(load_json(PORTFOLIO_V1, default))
    write_status_v3(load_json(PORTFOLIO_V3, default))

    print("Sync completato.")
