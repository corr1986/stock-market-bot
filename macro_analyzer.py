"""
Analisi macro: VIX, regime di mercato, performance settoriale settimanale.
Usato solo da main_v2.py — non modifica il comportamento di main.py (v1).
"""

import yfinance as yf

SECTOR_ETFS = {
    "AI/Tech":      "XLK",
    "Energia":      "XLE",
    "Rinnovabili":  "ICLN",
    "Robotica/AI":  "BOTZ",
    "Difesa":       "ITA",
    "Healthcare":   "XLV",
    "Finanza":      "XLF",
    "Consumo disc.":"XLY",
}

INDEX_BENCHMARKS = {
    "S&P 500":  "SPY",
    "Nasdaq":   "QQQ",
    "Europa":   "EFA",
}


def _weekly_change(ticker: str) -> float | None:
    try:
        df = yf.download(ticker, period="10d", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 2:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        start = float(df["Close"].iloc[-6]) if len(df) >= 6 else float(df["Close"].iloc[0])
        end = float(df["Close"].iloc[-1])
        return round((end - start) / start * 100, 2)
    except Exception:
        return None


def get_macro_context() -> dict:
    # VIX
    vix = None
    try:
        df = yf.download("^VIX", period="5d", interval="1d", progress=False, auto_adjust=True)
        if not df.empty:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            vix = round(float(df["Close"].iloc[-1]), 1)
    except Exception:
        pass

    if vix is None:
        regime = "Sconosciuto"
    elif vix < 15:
        regime = "Risk-On forte (mercato calmo, bassa volatilita')"
    elif vix < 20:
        regime = "Risk-On moderato"
    elif vix < 25:
        regime = "Neutro/Misto"
    elif vix < 35:
        regime = "Risk-Off (volatilita' elevata, cautela)"
    else:
        regime = "Risk-Off estremo (panico, evitare growth speculativo)"

    # Settori
    sector_perf = {}
    for name, etf in SECTOR_ETFS.items():
        chg = _weekly_change(etf)
        if chg is not None:
            sector_perf[name] = chg

    sorted_sectors = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
    hot_sectors  = [s[0] for s in sorted_sectors[:3] if s[1] > 0]
    weak_sectors = [s[0] for s in sorted_sectors if s[1] < 0][-2:]

    # Indici benchmark
    index_perf = {}
    for name, etf in INDEX_BENCHMARKS.items():
        chg = _weekly_change(etf)
        if chg is not None:
            index_perf[name] = chg

    return {
        "vix": vix,
        "regime": regime,
        "sectors": sorted_sectors,
        "hot_sectors": hot_sectors,
        "weak_sectors": weak_sectors,
        "indices": index_perf,
    }


def format_macro_for_prompt(ctx: dict) -> str:
    lines = ["=== CONTESTO MACRO ==="]
    lines.append(f"VIX: {ctx['vix']} — {ctx['regime']}")

    if ctx["indices"]:
        lines.append("\nIndici benchmark (variaz. settimanale):")
        for name, chg in ctx["indices"].items():
            sign = "+" if chg >= 0 else ""
            lines.append(f"  {name}: {sign}{chg}%")

    if ctx["sectors"]:
        lines.append("\nSettori (ETF, variaz. settimanale):")
        for name, chg in ctx["sectors"]:
            sign = "+" if chg >= 0 else ""
            lines.append(f"  {name}: {sign}{chg}%")

    if ctx["hot_sectors"]:
        lines.append(f"\nSettori in forza: {', '.join(ctx['hot_sectors'])}")
    if ctx["weak_sectors"]:
        lines.append(f"Settori deboli: {', '.join(ctx['weak_sectors'])}")

    return "\n".join(lines)
