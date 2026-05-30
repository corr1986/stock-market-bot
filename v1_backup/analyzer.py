import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import AverageTrueRange
from config import WATCHLIST_USA, WATCHLIST_EUROPE, WATCHLIST_INDICES, LOOKBACK_PERIOD, INTERVAL, PRE_FILTER_TOP_N


def fetch_data(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, period=LOOKBACK_PERIOD, interval=INTERVAL, progress=False)
    if df.empty:
        return None
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def compute_indicators(df: pd.DataFrame) -> dict:
    close = df["Close"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    rsi = RSIIndicator(close, window=14).rsi()
    macd_obj = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    sma20 = SMAIndicator(close, window=20).sma_indicator()
    sma50 = SMAIndicator(close, window=50).sma_indicator()
    atr = AverageTrueRange(high, low, close, window=14).average_true_range()

    last = close.iloc[-1]
    prev_week_close = close.iloc[-2] if len(close) >= 2 else close.iloc[0]
    weekly_change = (last - prev_week_close) / prev_week_close * 100

    avg_volume = volume.iloc[-20:].mean()
    last_volume = volume.iloc[-1]
    volume_ratio = last_volume / avg_volume if avg_volume > 0 else 1

    return {
        "price": round(float(last), 2),
        "weekly_change_pct": round(float(weekly_change), 2),
        "rsi_14": round(float(rsi.iloc[-1]), 1) if rsi is not None else None,
        "macd_line": round(float(macd_obj.macd().iloc[-1]), 4),
        "macd_signal": round(float(macd_obj.macd_signal().iloc[-1]), 4),
        "macd_hist": round(float(macd_obj.macd_diff().iloc[-1]), 4),
        "sma20": round(float(sma20.iloc[-1]), 2) if sma20 is not None else None,
        "sma50": round(float(sma50.iloc[-1]), 2) if sma50 is not None else None,
        "atr_14": round(float(atr.iloc[-1]), 2) if atr is not None else None,
        "volume_ratio": round(float(volume_ratio), 2),
        "above_sma20": bool(last > sma20.iloc[-1]) if sma20 is not None else None,
        "above_sma50": bool(last > sma50.iloc[-1]) if sma50 is not None else None,
    }


def score_stock(indicators: dict) -> float:
    """Punteggio tecnico rialzista: più alto = setup BUY più convincente."""
    score = 0.0

    rsi = indicators.get("rsi_14")
    macd_hist = indicators.get("macd_hist")
    above_sma20 = indicators.get("above_sma20")
    above_sma50 = indicators.get("above_sma50")
    volume_ratio = indicators.get("volume_ratio", 1.0)
    weekly_change = indicators.get("weekly_change_pct", 0)

    if rsi is not None:
        if 40 <= rsi <= 65:
            score += 2.0   # zona ideale: non ipercomprato, momentum presente
        elif rsi < 40:
            score += 0.5   # oversold: possibile rimbalzo ma meno affidabile
        elif rsi > 70:
            score -= 2.0   # ipercomprato: escludiamo

    if macd_hist is not None:
        if macd_hist > 0:
            score += 2.0   # momentum rialzista confermato
        else:
            score -= 1.0

    if above_sma20:
        score += 1.0
    if above_sma50:
        score += 1.5       # sopra SMA50 = trend primario rialzista

    if volume_ratio > 1.2:
        score += 1.0       # volume sopra media: forza
    elif volume_ratio > 1.0:
        score += 0.5

    if weekly_change > 2:
        score += 1.0
    elif weekly_change > 0:
        score += 0.5

    return score


def pre_filter_snapshot(snapshot: dict, top_n: int = PRE_FILTER_TOP_N) -> dict:
    """Seleziona i migliori candidati rialzisti da passare al LLM."""
    candidates = []

    for category, assets in snapshot.items():
        for ticker, indicators in assets.items():
            s = score_stock(indicators)
            candidates.append((category, ticker, indicators, s))

    candidates.sort(key=lambda x: x[3], reverse=True)
    top = candidates[:top_n]

    filtered = {"USA": {}, "EUROPE": {}, "INDICES": {}}
    for category, ticker, indicators, _ in top:
        filtered[category][ticker] = indicators

    return filtered


def get_top_signals(snapshot: dict, n: int = 3, sl_mult: float = 1.5, rr: float = 3.0) -> list:
    """Restituisce i top N candidati rialzisti con entry/SL/TP calcolati."""
    candidates = []
    for category, assets in snapshot.items():
        for ticker, ind in assets.items():
            score = score_stock(ind)
            if score > 0 and (ind.get("macd_hist") or 0) > 0:
                candidates.append((ticker, ind, score, category))

    candidates.sort(key=lambda x: x[2], reverse=True)

    signals = []
    for ticker, ind, score, category in candidates[:n]:
        entry = ind["price"]
        atr = ind.get("atr_14") or (entry * 0.015)
        sl = round(entry - sl_mult * atr, 4)
        tp = round(entry + rr * sl_mult * atr, 4)
        signals.append({
            "ticker": ticker,
            "category": category,
            "entry_price": entry,
            "sl": sl,
            "tp": tp,
            "atr": round(atr, 4),
            "score": round(score, 2),
        })

    return signals


def build_market_snapshot() -> dict:
    snapshot = {"USA": {}, "EUROPE": {}, "INDICES": {}}

    for ticker in WATCHLIST_USA:
        df = fetch_data(ticker)
        if df is not None:
            snapshot["USA"][ticker] = compute_indicators(df)

    for ticker in WATCHLIST_EUROPE:
        df = fetch_data(ticker)
        if df is not None:
            snapshot["EUROPE"][ticker] = compute_indicators(df)

    for yahoo_ticker, name in WATCHLIST_INDICES.items():
        df = fetch_data(yahoo_ticker)
        if df is not None:
            data = compute_indicators(df)
            data["name"] = name
            snapshot["INDICES"][yahoo_ticker] = data

    return snapshot
