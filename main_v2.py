"""
Stock Market Bot v2 — aggiunge contesto macro e notizie alla selezione segnali.
NON e' schedulato: va eseguito manualmente per confronto con v1.
Non modifica portfolio.json (solo osservazione, senza aprire posizioni).
"""

import sys
from datetime import datetime
from analyzer import build_market_snapshot, pre_filter_snapshot
from macro_analyzer import get_macro_context, format_macro_for_prompt
from news_fetcher import get_news_for_candidates, get_sectors_for_candidates, format_news_for_prompt
from claude_analyst_v2 import generate_report
from notifier import send_telegram


def run():
    today = datetime.now().strftime("%d/%m/%Y")
    today_iso = datetime.now().strftime("%Y-%m-%d")
    print(f"[{today}] Stock Market Bot v2 avviato")

    # 1. Dati tecnici (identico a v1)
    print("Scaricamento dati di mercato...")
    snapshot = build_market_snapshot()
    usa_count   = len(snapshot["USA"])
    eu_count    = len(snapshot["EUROPE"])
    idx_count   = len(snapshot["INDICES"])
    total       = usa_count + eu_count + idx_count
    print(f"Dati raccolti: {idx_count} indici, {usa_count} USA, {eu_count} Europa ({total} totali)")

    if total == 0:
        print("Nessun dato. Uscita.")
        sys.exit(1)

    print("Pre-filtro tecnico...")
    filtered = pre_filter_snapshot(snapshot)
    kept = sum(len(v) for v in filtered.values())
    print(f"Candidati dopo pre-filtro: {kept} su {total}")

    # 2. Contesto macro (NUOVO)
    print("Analisi macro (VIX + settori)...")
    macro_ctx = get_macro_context()
    macro_str = format_macro_for_prompt(macro_ctx)
    print(f"  VIX: {macro_ctx['vix']} | Regime: {macro_ctx['regime']}")
    if macro_ctx["hot_sectors"]:
        print(f"  Settori forti: {', '.join(macro_ctx['hot_sectors'])}")
    if macro_ctx["weak_sectors"]:
        print(f"  Settori deboli: {', '.join(macro_ctx['weak_sectors'])}")

    # 3. Notizie candidati (NUOVO)
    all_tickers = [t for cat in filtered.values() for t in cat.keys()]
    # escludi indici dalla ricerca news (ticker come ^GSPC non hanno news utili)
    stock_tickers = [t for t in all_tickers if not t.startswith("^")]
    print(f"Download notizie per {len(stock_tickers)} candidati...")
    news    = get_news_for_candidates(stock_tickers, max_per_ticker=4)
    sectors = get_sectors_for_candidates(stock_tickers)
    news_str = format_news_for_prompt(news, sectors)
    print(f"  Notizie trovate per {len(news)} ticker su {len(stock_tickers)}")

    # 4. Analisi LLM v2
    print("Analisi LLM v2 in corso...")
    report = generate_report(filtered, today, macro_str, news_str)

    # 5. Telegram — prefisso [V2 TEST] per distinguere da v1
    header = f"*[V2 TEST] Stock Market Bot — {today}*\n\n"
    full_message = header + report
    print("Invio report v2 su Telegram...")
    ok = send_telegram(full_message)
    if ok:
        print("Report v2 inviato.")
    else:
        print("Errore invio Telegram.")
        sys.exit(1)

    print("\n--- REPORT V2 ---")
    print(report)
    print("-----------------")
    print("NOTA: v2 non apre posizioni nel portfolio. Confronta i segnali con quelli di v1.")


if __name__ == "__main__":
    run()
