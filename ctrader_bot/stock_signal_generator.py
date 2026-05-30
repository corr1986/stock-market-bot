# StockMarketBot -- Signal Generator per cTrader
# Ogni lunedi alle 08:00 UTC: scarica dati weekly, calcola indicatori,
# seleziona top 3 titoli e scrive stock_signals.json per il cBot C#.
#
# VPS path:   C:/Users/Administrator/Desktop/trading_bot_ctrader/StockMarketBot/
# Bridge out: C:/TradeBridge/StockBot/stock_signals.json
#
# Richiede: pip install yfinance pandas ta numpy

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import AverageTrueRange

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

BRIDGE_PATH  = r"C:\TradeBridge\StockBot\stock_signals.json"
LOG_PATH     = r"C:\TradeBridge\StockBot\stock_signal_generator.log"

SL_MULT             = 1.5    # ATR multiplier per SL
RR                  = 4.0    # Risk/Reward (Bloomberg V2 sweet spot)
TOP_N               = 3      # Numero di segnali da generare
PRE_FILTER_BLOOMBERG_N = 20  # top-20 tecnici prima del re-ranking Bloomberg
MIN_SCORE    = 0.0    # Score minimo
MIN_BARS     = 26     # Barre minime richieste

# ---------------------------------------------------------------------------
# Mapping yfinance → cTrader (FPMarkets)
# ---------------------------------------------------------------------------

YF_TO_CT = {
    # USA — NASDAQ
    "AAPL":  "AAPL.xnas",  "MSFT":  "MSFT.xnas",  "NVDA":  "NVDA.xnas",
    "GOOGL": "GOOGL.xnas", "GOOG":  "GOOG.xnas",   "META":  "META.xnas",
    "AMZN":  "AMZN.xnas",  "TSLA":  "TSLA.xnas",   "AVGO":  "AVGO.xnas",
    "AMD":   "AMD.xnas",   "QCOM":  "QCOM.xnas",   "TXN":   "TXN.xnas",
    "ADI":   "ADI.xnas",   "MU":    "MU.xnas",     "AMAT":  "AMAT.xnas",
    "KLAC":  "KLAC.xnas",  "SNPS":  "SNPS.xnas",   "CDNS":  "CDNS.xnas",
    "NXPI":  "NXPI.xnas",  "MRVL":  "MRVL.xnas",   "INTC":  "INTC.xnas",
    "ADBE":  "ADBE.xnas",  "INTU":  "INTU.xnas",   "CSCO":  "CSCO.xnas",
    "FTNT":  "FTNT.xnas",  "DDOG":  "DDOG.xnas",   "OKTA":  "OKTA.xnas",
    "ZM":    "ZM.xnas",    "TWLO":  "TWLO.xnas",   "DOCU":  "DOCU.xnas",
    "WDAY":  "WDAY.xnas",  "SPLK":  "SPLK.xnas",   "PANW":  "PANW.xnas",
    "NFLX":  "NFLX.xnas",  "MELI":  "MELI.xnas",   "BKNG":  "BKNG.xnas",
    "EBAY":  "EBAY.xnas",  "TTD":   "TTD.xnas",    "ROKU":  "ROKU.xnas",
    "PYPL":  "PYPL.xnas",  "AMGN":  "AMGN.xnas",   "GILD":  "GILD.xnas",
    "VRTX":  "VRTX.xnas",  "REGN":  "REGN.xnas",   "BIIB":  "BIIB.xnas",
    "ILMN":  "ILMN.xnas",  "ISRG":  "ISRG.xnas",   "IDXX":  "IDXX.xnas",
    "DXCM":  "DXCM.xnas",  "PEP":   "PEP.xnas",    "COST":  "COST.xnas",
    "MAR":   "MAR.xnas",   "EA":    "EA.xnas",     "TTWO":  "TTWO.xnas",
    "ATVI":  "ATVI.xnas",  "HON":   "HON.xnas",    "EQIX":  "EQIX.xnas",
    "MDLZ":  "MDLZ.xnas",  "AEP":   "AEP.xnas",    "CME":   "CME.xnas",
    # USA — NYSE
    "CRM":   "CRM.xnys",   "NOW":   "NOW.xnys",    "ORCL":  "ORCL.xnys",
    "IBM":   "IBM.xnys",   "SNOW":  "SNOW.xnys",   "V":     "V.xnys",
    "MA":    "MA.xnys",    "SQ":    "SQ.xnys",     "AXP":   "AXP.xnys",
    "LLY":   "LLY.xnys",   "ABBV":  "ABBV.xnys",   "MRK":   "MRK.xnys",
    "ABT":   "ABT.xnys",   "BMY":   "BMY.xnys",    "PFE":   "PFE.xnys",
    "JNJ":   "JNJ.xnys",   "MRNA":  "MRNA.xnys",   "UNH":   "UNH.xnys",
    "TMO":   "TMO.xnys",   "DHR":   "DHR.xnys",    "MDT":   "MDT.xnys",
    "BSX":   "BSX.xnys",   "BDX":   "BDX.xnys",    "SYK":   "SYK.xnys",
    "HUM":   "HUM.xnys",   "CI":    "CI.xnys",     "EW":    "EW.xnys",
    "CVS":   "CVS.xnys",   "A":     "A.xnys",      "ELV":   "ELV.xnys",
    "JPM":   "JPM.xnys",   "BAC":   "BAC.xnys",    "GS":    "GS.xnys",
    "MS":    "MS.xnys",    "BLK":   "BLK.xnys",    "C":     "C.xnys",
    "CB":    "CB.xnys",    "SCHW":  "SCHW.xnys",   "SPGI":  "SPGI.xnys",
    "MCO":   "MCO.xnys",   "ICE":   "ICE.xnys",    "USB":   "USB.xnys",
    "PGR":   "PGR.xnys",   "PRU":   "PRU.xnys",    "MET":   "MET.xnys",
    "AFL":   "AFL.xnys",   "TRV":   "TRV.xnys",    "PNC":   "PNC.xnys",
    "DFS":   "DFS.xnys",   "COF":   "COF.xnys",    "MMC":   "MMC.xnys",
    "BK":    "BK.xnys",    "PG":    "PG.xnys",     "KO":    "KO.xnys",
    "WMT":   "WMT.xnys",   "PM":    "PM.xnys",     "MCD":   "MCD.xnys",
    "SBUX":  "SBUX.xnys",  "KMB":   "KMB.xnys",    "CL":    "CL.xnys",
    "GIS":   "GIS.xnys",   "KR":    "KR.xnys",     "HSY":   "HSY.xnys",
    "YUM":   "YUM.xnys",   "HD":    "HD.xnys",     "LOW":   "LOW.xnys",
    "TJX":   "TJX.xnys",   "NKE":   "NKE.xnys",    "RACE":  "RACE.xnys",
    "HLT":   "HLT.xnys",   "SNAP":  "SNAP.xnys",   "PINS":  "PINS.xnys",
    "SPOT":  "SPOT.xnys",  "SHOP":  "SHOP.xnys",   "UBER":  "UBER.xnys",
    "DIS":   "DIS.xnys",   "XOM":   "XOM.xnys",    "CVX":   "CVX.xnys",
    "EOG":   "EOG.xnys",   "COP":   "COP.xnys",    "OXY":   "OXY.xnys",
    "DVN":   "DVN.xnys",   "HAL":   "HAL.xnys",    "SLB":   "SLB.xnys",
    "VLO":   "VLO.xnys",   "MPC":   "MPC.xnys",    "PSX":   "PSX.xnys",
    "WMB":   "WMB.xnys",   "OKE":   "OKE.xnys",    "KMI":   "KMI.xnys",
    "CAT":   "CAT.xnys",   "DE":    "DE.xnys",     "GE":    "GE.xnys",
    "ETN":   "ETN.xnys",   "ITW":   "ITW.xnys",    "EMR":   "EMR.xnys",
    "WM":    "WM.xnys",    "MMM":   "MMM.xnys",    "RTX":   "RTX.xnys",
    "NOC":   "NOC.xnys",   "LMT":   "LMT.xnys",    "LHX":   "LHX.xnys",
    "FDX":   "FDX.xnys",   "UPS":   "UPS.xnys",    "CSX":   "CSX.xnys",
    "UNP":   "UNP.xnys",   "GD":    "GD.xnys",     "ROK":   "ROK.xnys",
    "CMI":   "CMI.xnys",   "SHW":   "SHW.xnys",    "DOW":   "DOW.xnys",
    "DD":    "DD.xnys",    "LYB":   "LYB.xnys",    "ECL":   "ECL.xnys",
    "FCX":   "FCX.xnys",   "NEM":   "NEM.xnys",    "PPG":   "PPG.xnys",
    "NEE":   "NEE.xnys",   "DUK":   "DUK.xnys",    "SO":    "SO.xnys",
    "D":     "D.xnys",     "EXC":   "EXC.xnys",    "DTE":   "DTE.xnys",
    "SRE":   "SRE.xnys",   "PLD":   "PLD.xnys",    "AMT":   "AMT.xnys",
    "CCI":   "CCI.xnys",   "PSA":   "PSA.xnys",    "EQR":   "EQR.xnys",
    "AVB":   "AVB.xnys",   "TSM":   "TSM.xnys",
    # Europa — Germania (ETR)
    "ADS.DE":  "ADS.ETR",  "ALV.DE":  "ALV.ETR",   "BAS.DE":  "BAS.ETR",
    "BAYN.DE": "BAYN.ETR", "BEI.DE":  "BEI.ETR",   "BMW.DE":  "BMW.ETR",
    "CON.DE":  "CON.ETR",  "DBK.DE":  "DBK.ETR",   "DB1.DE":  "DB1.ETR",
    "EOAN.DE": "EOAN.ETR", "FRE.DE":  "FRE.ETR",   "HEN3.DE": "HEN3.ETR",
    "IFX.DE":  "IFX.ETR",  "MRK.DE":  "MRK.ETR",   "MTX.DE":  "MTX.ETR",
    "MUV2.DE": "MUV2.ETR", "RWE.DE":  "RWE.ETR",   "SAP.DE":  "SAP.ETR",
    "SIE.DE":  "SIE.ETR",  "SHL.DE":  "SHL.ETR",   "VNA.DE":  "VNA.ETR",
    "VOW3.DE": "VOW3.ETR",
    # Europa — Paesi Bassi (xams)
    "AGN.AS":  "AGN.xams", "ASM.AS":  "ASM.xams",  "ASML.AS": "ASML.xams",
    "HEIA.AS": "HEIA.xams","IMCD.AS": "IMCD.xams",  "NN.AS":   "NN.xams",
    "PHIA.AS": "PHIA.xams","RAND.AS": "RAND.xams",  "REL.AS":  "REL.xams",
    "AD.AS":   "AD.xams",  "WKL.AS":  "WKL.xams",
    # Europa — Francia (xpar)
    "AI.PA":  "AI.xpar",   "AIR.PA": "AIR.xpar",   "BNP.PA": "BNP.xpar",
    "GLE.PA": "GLE.xpar",  "KER.PA": "KER.xpar",   "MC.PA":  "MC.xpar",
    "OR.PA":  "OR.xpar",   "PUB.PA": "PUB.xpar",   "RMS.PA": "RMS.xpar",
    "SAN.PA": "SAN.xpar",  "SU.PA":  "SU.xpar",    "TTE.PA": "TTE.xpar",
    # Europa — Spagna (xmad)
    "ACS.MC": "ACS.xmad",  "ANA.MC": "ANA.xmad",   "BBVA.MC": "BBVA.xmad",
    "IBE.MC": "IBE.xmad",  "ITX.MC": "ITX.xmad",   "REP.MC":  "REP.xmad",
    "SAN.MC": "SAN.xmad",
    # Europa — UK (xlon) — NOTA: LLOY→LLOYDS, SHEL→RDSA su FPMarkets
    "BARC.L": "BARC.xlon", "BP.L":   "BP.xlon",    "GLEN.L": "GLEN.xlon",
    "GSK.L":  "GSK.xlon",  "HSBA.L": "HSBA.xlon",  "LLOY.L": "LLOYDS.xlon",
    "NWG.L":  "NWG.xlon",  "RIO.L":  "RIO.xlon",   "SHEL.L": "RDSA.xlon",
    "STAN.L": "STAN.xlon",
}

# Watchlist completa (yfinance symbols)
WATCHLIST = list(YF_TO_CT.keys())

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg):
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Indicatori tecnici (stessa logica di analyzer.py)
# ---------------------------------------------------------------------------

def compute_indicators(df: pd.DataFrame) -> dict:
    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    rsi     = RSIIndicator(close, window=14).rsi()
    macd_obj = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    sma20   = SMAIndicator(close, window=20).sma_indicator()
    sma50   = SMAIndicator(close, window=50).sma_indicator()
    atr     = AverageTrueRange(high, low, close, window=14).average_true_range()

    last          = float(close.iloc[-1])
    prev          = float(close.iloc[-2]) if len(close) >= 2 else last
    weekly_change = (last - prev) / prev * 100

    avg_vol    = float(volume.iloc[-20:].mean())
    last_vol   = float(volume.iloc[-1])
    vol_ratio  = last_vol / avg_vol if avg_vol > 0 else 1.0

    return {
        "price":            round(last, 4),
        "weekly_change_pct": round(weekly_change, 2),
        "rsi_14":           round(float(rsi.iloc[-1]), 1),
        "macd_hist":        round(float(macd_obj.macd_diff().iloc[-1]), 6),
        "sma20":            round(float(sma20.iloc[-1]), 4),
        "sma50":            round(float(sma50.iloc[-1]), 4),
        "atr_14":           round(float(atr.iloc[-1]), 6),
        "volume_ratio":     round(vol_ratio, 2),
        "above_sma20":      bool(last > float(sma20.iloc[-1])),
        "above_sma50":      bool(last > float(sma50.iloc[-1])),
    }


def score_stock(ind: dict) -> float:
    score = 0.0
    rsi          = ind.get("rsi_14")
    macd_hist    = ind.get("macd_hist")
    above_sma20  = ind.get("above_sma20")
    above_sma50  = ind.get("above_sma50")
    vol_ratio    = ind.get("volume_ratio", 1.0)
    weekly_chg   = ind.get("weekly_change_pct", 0)

    if rsi is not None:
        if 40 <= rsi <= 65:   score += 2.0
        elif rsi < 40:        score += 0.5
        elif rsi > 70:        score -= 2.0

    if macd_hist is not None:
        score += 2.0 if macd_hist > 0 else -1.0

    if above_sma20:  score += 1.0
    if above_sma50:  score += 1.5

    if   vol_ratio > 1.2: score += 1.0
    elif vol_ratio > 1.0: score += 0.5

    if   weekly_chg > 2: score += 1.0
    elif weekly_chg > 0: score += 0.5

    return score


def bloomberg_enhanced_score(ind: dict) -> float:
    """Bloomberg proxy re-ranking — validato da backtest (+€2k vs V1 su 6 anni)."""
    base   = score_stock(ind)
    rsi    = ind.get("rsi_14") or 0
    vol    = ind.get("volume_ratio") or 0
    change = ind.get("weekly_change_pct") or 0
    sma50  = ind.get("above_sma50") or False

    bonus = 0.0
    if vol >= 1.5:           bonus += 2.0
    elif vol >= 1.2:         bonus += 0.5
    if 50 <= rsi <= 62:      bonus += 1.5
    elif 48 <= rsi < 50:     bonus += 0.5
    elif rsi > 65:           bonus -= 2.0
    if change >= 2.0:        bonus += 1.5
    elif change >= 1.0:      bonus += 0.5
    if sma50:                bonus += 1.0

    return base + bonus

# ---------------------------------------------------------------------------
# Download dati
# ---------------------------------------------------------------------------

def fetch_weekly(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period="3y", interval="1wk",
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Generazione segnali
# ---------------------------------------------------------------------------

def generate_signals() -> list:
    log(f"Download dati weekly per {len(WATCHLIST)} titoli...")
    candidates = []
    ok = skip = 0

    for yf_sym in WATCHLIST:
        ct_sym = YF_TO_CT.get(yf_sym)
        if not ct_sym:
            continue

        df = fetch_weekly(yf_sym)
        if df is None or len(df) < MIN_BARS:
            skip += 1
            continue

        try:
            ind   = compute_indicators(df)
            score = score_stock(ind)
            if score > MIN_SCORE and (ind.get("macd_hist") or 0) > 0:
                candidates.append((yf_sym, ct_sym, ind, score))
            ok += 1
        except Exception as e:
            log(f"  Errore {yf_sym}: {e}")
            skip += 1

    log(f"  Elaborati: {ok} | Saltati: {skip} | Candidati: {len(candidates)}")

    # Step 1: top-20 per score tecnico
    candidates.sort(key=lambda x: x[3], reverse=True)
    top20 = candidates[:PRE_FILTER_BLOOMBERG_N]

    # Step 2: re-ranking Bloomberg enhanced
    top20.sort(key=lambda x: bloomberg_enhanced_score(x[2]), reverse=True)

    signals = []
    for yf_sym, ct_sym, ind, score in top20[:TOP_N]:
        price = ind["price"]
        atr   = ind["atr_14"] or (price * 0.015)
        sl_abs = SL_MULT * atr
        tp_abs = RR * SL_MULT * atr
        sl_pct = round(sl_abs / price * 100, 4)
        tp_pct = round(tp_abs / price * 100, 4)

        signals.append({
            "yf_symbol": yf_sym,
            "ct_symbol": ct_sym,
            "ref_price": price,
            "sl_pct":    sl_pct,
            "tp_pct":    tp_pct,
            "score":     round(score, 2),
        })
        bl = bloomberg_enhanced_score(ind)
        log(f"  OK {yf_sym} ({ct_sym}) score={score:.2f} bl={bl:.2f} SL=-{sl_pct:.2f}% TP=+{tp_pct:.2f}%")

    return signals

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log("=" * 60)
    log("StockMarketBot — Signal Generator avviato")

    now  = datetime.now(timezone.utc)
    week = now.strftime("%Y-W%V")
    log(f"Settimana: {week}")

    signals = generate_signals()

    if not signals:
        log("ATTENZIONE: nessun segnale generato questa settimana.")

    payload = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week":         week,
        "signals":      signals,
    }

    os.makedirs(os.path.dirname(BRIDGE_PATH), exist_ok=True)
    with open(BRIDGE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    log(f"Segnali scritti in: {BRIDGE_PATH}")
    log(f"Totale segnali: {len(signals)}")
    log("=" * 60)
