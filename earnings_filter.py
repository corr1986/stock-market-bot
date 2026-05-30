from datetime import datetime, timedelta
import yfinance as yf


def has_earnings_soon(ticker: str, days: int = 14) -> bool:
    """True se il ticker ha earnings entro `days` giorni. False su errore o dati mancanti."""
    try:
        cal = yf.Ticker(ticker).calendar
        if not cal or "Earnings Date" not in cal:
            return False
        dates = cal["Earnings Date"]
        if not dates:
            return False
        cutoff = datetime.now() + timedelta(days=days)
        return any(d <= cutoff for d in dates if hasattr(d, 'year'))
    except Exception:
        return False
