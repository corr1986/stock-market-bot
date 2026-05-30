"""
Scarica notizie recenti e settore di appartenenza per i candidati top.
Usa yfinance.Ticker.news — zero API key aggiuntive.
Usato solo da main_v2.py.
"""

import yfinance as yf


def get_ticker_news(ticker: str, max_items: int = 5) -> list:
    try:
        news = yf.Ticker(ticker).news or []
        headlines = []
        for item in news[:max_items]:
            title = (item.get("content") or {}).get("title") or item.get("title", "")
            if title:
                headlines.append(title)
        return headlines
    except Exception:
        return []


def get_ticker_sector(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector") or info.get("industryDisp") or ""
        return sector
    except Exception:
        return ""


def get_news_for_candidates(tickers: list, max_per_ticker: int = 4) -> dict:
    result = {}
    for ticker in tickers:
        headlines = get_ticker_news(ticker, max_per_ticker)
        if headlines:
            result[ticker] = headlines
    return result


def get_sectors_for_candidates(tickers: list) -> dict:
    result = {}
    for ticker in tickers:
        sector = get_ticker_sector(ticker)
        if sector:
            result[ticker] = sector
    return result


def format_news_for_prompt(news: dict, sectors: dict) -> str:
    if not news and not sectors:
        return ""
    lines = ["=== NOTIZIE RECENTI SUI CANDIDATI ==="]
    all_tickers = set(list(news.keys()) + list(sectors.keys()))
    for ticker in sorted(all_tickers):
        sector_str = f" [{sectors[ticker]}]" if ticker in sectors else ""
        lines.append(f"\n{ticker}{sector_str}:")
        for headline in news.get(ticker, []):
            lines.append(f"  - {headline}")
        if ticker not in news:
            lines.append("  (nessuna notizia recente)")
    return "\n".join(lines)
