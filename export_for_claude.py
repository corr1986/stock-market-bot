"""
export_for_claude.py
--------------------
Esegue il pre-filtro tecnico della watchlist e genera un testo
pronto da incollare in Claude.ai per l'analisi qualitativa enriched.

Uso:
    python export_for_claude.py

Output:
    - screen_YYYYMMDD.txt nella stessa cartella
    - testo stampato a console (copia/incolla in Claude.ai)
"""

import sys
import os
from datetime import date

# Assicura che i moduli del bot siano importabili
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import build_market_snapshot, pre_filter_snapshot
from config import PRE_FILTER_TOP_N


def format_snapshot_for_claude(filtered: dict, today: str, total: int) -> str:
    count = sum(len(v) for v in filtered.values())

    lines = []
    lines.append(f"WATCHLIST SCREEN — {today}")
    lines.append(f"Top {count} candidati tecnici su {total} analizzati")
    lines.append("=" * 55)

    for category, tickers in filtered.items():
        if not tickers:
            continue
        lines.append(f"\n### {category} ({len(tickers)} titoli)\n")

        for ticker, ind in tickers.items():
            rsi     = ind.get("rsi_14", "N/A")
            macd_h  = ind.get("macd_hist") or 0
            macd_s  = "rialzista" if macd_h > 0 else "ribassista"
            sma20   = "✓" if ind.get("above_sma20") else "✗"
            sma50   = "✓" if ind.get("above_sma50") else "✗"
            vol     = ind.get("volume_ratio", 1.0)
            change  = ind.get("weekly_change_pct", 0.0)
            price   = ind.get("price", 0.0)
            atr     = ind.get("atr_14", 0.0)

            lines.append(
                f"  {ticker:<12} "
                f"Prezzo: {price:>8.2f} | "
                f"Var.sett: {change:>+5.1f}% | "
                f"RSI: {rsi:>4} | "
                f"MACD: {macd_s:<11} | "
                f"SMA20:{sma20} SMA50:{sma50} | "
                f"Vol: {vol:.1f}x | "
                f"ATR: {atr:.2f}"
            )

    lines.append("\n" + "=" * 55)
    lines.append("ISTRUZIONI PER CLAUDE:")
    lines.append(
        "Per ciascun titolo sopra:\n"
        "1. Cerca notizie recenti (ultimi 7 giorni)\n"
        "2. Verifica la data del prossimo earnings report\n"
        "3. Controlla consensus analisti (Buy/Hold/Sell, target price)\n"
        "4. Valuta il contesto macro del settore\n"
        "5. Assegna rating: STRONG BUY / BUY / WATCH / SKIP\n\n"
        "Output: lista ordinata per priorità.\n"
        "Per ogni STRONG BUY o BUY includi: news chiave, prossimo earnings, "
        "consensus, motivo del rating.\n"
        "Massimo 5 titoli raccomandati (STRONG BUY + BUY).\n"
        "Se nessun titolo merita BUY, scrivi solo: 'Nessun setup convincente questa settimana.'"
    )

    return "\n".join(lines)


def main():
    today = date.today().strftime("%d/%m/%Y")
    total_universe = 253  # 191 USA + 62 Europa + indici non contati nello screen

    print(f"[{today}] Costruendo snapshot mercato — può richiedere 2-3 minuti...")
    snapshot = build_market_snapshot()

    print(f"Applicando pre-filtro tecnico (top {PRE_FILTER_TOP_N})...")
    filtered = pre_filter_snapshot(snapshot)

    output = format_snapshot_for_claude(filtered, today, total_universe)

    # Salva su file
    filename = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"screen_{date.today().strftime('%Y%m%d')}.txt"
    )
    with open(filename, "w", encoding="utf-8") as f:
        f.write(output)

    # Prova a copiare negli appunti (opzionale, richiede pyperclip)
    try:
        import pyperclip
        pyperclip.copy(output)
        print("Copiato negli appunti!\n")
    except ImportError:
        print(f"(pyperclip non installato — copia manuale da: {filename})\n")

    print(output)
    print(f"\nFile salvato: {filename}")


if __name__ == "__main__":
    main()
