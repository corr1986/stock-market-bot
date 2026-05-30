"""
backtest_13f.py
---------------
Confronto Bloomberg V2 con e senza 13F Institutional Signal (versione espansa: 6 istituzioni)

Fonte dati: SEC EDGAR (gratuito, ufficiale)
  - Scarica 13F-HR filings per 6 gestori istituzionali USA
  - Traccia variazione QoQ del numero di istituzioni che detengono ogni ticker
  - Segnale positivo se il coverage istituzionale cresce nel trimestre

Istituzioni incluse (V2 espansa):
  Vanguard (passivo), State Street (passivo)
  Wellington (attivo ~1750 pos), Capital Research (attivo ~430 pos)
  MFS (attivo aggregato ~4000 pos), AllianceBernstein (attivo aggregato ~3250 pos)

Signal logic:
  +2.0 pts: ≥ 4 istituzioni aumentano posizione nel trimestre (forte accumulazione)
  +1.5 pts: 2-3 istituzioni aumentano posizione
  +1.0 pts: 1 istituzione aumenta posizione, aumento > 10%
  0.0 pts: nessuna variazione o riduzione

Universo: 186 ticker USA (WATCHLIST_USA)
Periodo:  2020-01-01 → 2026-04-30 (6.33 anni)
Capitale: 20.000 EUR | Trade size: 500 EUR
Cache:    market_data.pkl + inst13f_cache.pkl
"""

import os
import re
import sys
import pickle
import time
import html
import xml.etree.ElementTree as ET
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

from analyzer import compute_indicators, score_stock
from config import WATCHLIST_USA

# ---------------------------------------------------------------------------
# Parametri
# ---------------------------------------------------------------------------

CAPITAL       = 20_000
TRADE_SIZE    = 500
SAFETY_CAP    = 52
MIN_BARS      = 26
PRE_FILTER_N  = 20
TOP_N         = 3

BT_START = "2020-01-01"
BT_END   = "2026-04-30"

SL_MULT        = 2.0
RR             = 2.0
COMMISSION_EUR = 2.0

# 13F signal: lag minimo di 45 giorni dalla fine del trimestre (SEC deadline)
FILING_LAG_DAYS = 50   # usiamo 50gg come margine sicuro

# Bonus score
INST_BONUS_STRONG   = 2.0  # ≥ 4 istituzioni aggiungono
INST_BONUS_MEDIUM   = 1.5  # 2-3 istituzioni aggiungono
INST_BONUS_WEAK     = 1.0  # 1 istituzione aggiunge con >10%

CACHE_PRICE = os.path.join(os.path.dirname(__file__), "market_data.pkl")
CACHE_13F   = os.path.join(os.path.dirname(__file__), "inst13f_cache.pkl")

# ---------------------------------------------------------------------------
# Top istituzioni: (nome, CIK SEC EDGAR)
# CIK verificati via https://data.sec.gov/submissions/CIK{cik}.json
# Nota: si usano solo istituzioni con 13F-HR confermato e XML parsabile.
# ---------------------------------------------------------------------------

TOP_INSTITUTIONS = {
    # --- Gestori con accesso XML diretto (veloci, ~1-3s per filing) ---
    # Configurazione ottimale da backtest (2020-2026): +1.0%/anno vs Puro
    # Hedge fund testati (12 aggiunti) → risultato PEGGIORE (-1.1%/anno): esclusi
    # Index/passivi: coprono tutti i titoli S&P500 sempre (baseline)
    "Vanguard":     "0000102909",   # Vanguard Group Inc — 13F_CIK_date.xml
    "StateStreet":  "0000093751",   # State Street Corp  — XML_Infotable.xml
    # Attivi selettivi: selezione selettiva dei titoli (segnale più informativo)
    "Wellington":   "0000902219",   # Wellington Management Group LLP — form13fInfoTable.xml
    "CapResearch":  "0001422848",   # Capital Research Global Investors — form13fInfoTable.xml
}

SEC_HEADERS = {
    "User-Agent": "corradocuri@gmail.com research",
    "Accept-Encoding": "gzip, deflate",
}

# ---------------------------------------------------------------------------
# Name mapping: ticker → parole chiave per match col nome in 13F
# Le 13F usano nomi tipo "APPLE INC", "MICROSOFT CORP", "NVIDIA CORP"
# ---------------------------------------------------------------------------

TICKER_NAME_KEYWORDS = {
    "AAPL":  ["APPLE INC"],
    "MSFT":  ["MICROSOFT"],
    "NVDA":  ["NVIDIA"],
    "GOOGL": ["ALPHABET"],
    "GOOG":  ["ALPHABET"],
    "META":  ["META PLATFORMS", "FACEBOOK"],
    "AMZN":  ["AMAZON"],
    "TSLA":  ["TESLA"],
    "AVGO":  ["BROADCOM"],
    "AMD":   ["ADVANCED MICRO"],
    "QCOM":  ["QUALCOMM"],
    "TXN":   ["TEXAS INSTRUMENTS"],
    "ADI":   ["ANALOG DEVICES"],
    "MU":    ["MICRON"],
    "AMAT":  ["APPLIED MATERIALS"],
    "KLAC":  ["KLA"],
    "SNPS":  ["SYNOPSYS"],
    "NXPI":  ["NXP SEMICONDUCTORS"],
    "MRVL":  ["MARVELL"],
    "INTC":  ["INTEL"],
    "CDNS":  ["CADENCE"],
    "CRM":   ["SALESFORCE"],
    "ADBE":  ["ADOBE"],
    "NOW":   ["SERVICENOW"],
    "PANW":  ["PALO ALTO"],
    "INTU":  ["INTUIT"],
    "ORCL":  ["ORACLE"],
    "IBM":   ["INTERNATIONAL BUSINESS"],
    "CSCO":  ["CISCO"],
    "FTNT":  ["FORTINET"],
    "DDOG":  ["DATADOG"],
    "ZM":    ["ZOOM VIDEO"],
    "WDAY":  ["WORKDAY"],
    "OKTA":  ["OKTA"],
    "DOCU":  ["DOCUSIGN"],
    "SNOW":  ["SNOWFLAKE"],
    "TWLO":  ["TWILIO"],
    "NFLX":  ["NETFLIX"],
    "DIS":   ["WALT DISNEY", "DISNEY"],
    "SPOT":  ["SPOTIFY"],
    "SHOP":  ["SHOPIFY"],
    "MELI":  ["MERCADOLIBRE"],
    "BKNG":  ["BOOKING HOLDINGS", "BOOKING"],
    "EBAY":  ["EBAY"],
    "UBER":  ["UBER"],
    "TTD":   ["TRADE DESK"],
    "SNAP":  ["SNAP INC"],
    "PINS":  ["PINTEREST"],
    "ROKU":  ["ROKU"],
    "HD":    ["HOME DEPOT"],
    "LOW":   ["LOWES", "LOWE'S"],
    "TJX":   ["TJX"],
    "NKE":   ["NIKE"],
    "RACE":  ["FERRARI"],
    "MAR":   ["MARRIOTT"],
    "HLT":   ["HILTON"],
    "EA":    ["ELECTRONIC ARTS"],
    "TTWO":  ["TAKE-TWO", "TAKE TWO"],
    "V":     ["VISA INC"],
    "MA":    ["MASTERCARD"],
    "PYPL":  ["PAYPAL"],
    "AXP":   ["AMERICAN EXPRESS"],
    "LLY":   ["ELI LILLY"],
    "ABBV":  ["ABBVIE"],
    "MRK":   ["MERCK & CO", "MERCK"],
    "ABT":   ["ABBOTT"],
    "AMGN":  ["AMGEN"],
    "GILD":  ["GILEAD"],
    "VRTX":  ["VERTEX PHARMACEUTICALS", "VERTEX PHARMA"],
    "REGN":  ["REGENERON"],
    "PFE":   ["PFIZER"],
    "JNJ":   ["JOHNSON & JOHNSON", "JOHNSON"],
    "MRNA":  ["MODERNA"],
    "BIIB":  ["BIOGEN"],
    "BMY":   ["BRISTOL-MYERS", "BRISTOL MYERS"],
    "ILMN":  ["ILLUMINA"],
    "UNH":   ["UNITEDHEALTH"],
    "TMO":   ["THERMO FISHER"],
    "DHR":   ["DANAHER"],
    "ISRG":  ["INTUITIVE SURGICAL"],
    "MDT":   ["MEDTRONIC"],
    "BSX":   ["BOSTON SCIENTIFIC"],
    "BDX":   ["BECTON DICKINSON", "BECTON"],
    "SYK":   ["STRYKER"],
    "ELV":   ["ELEVANCE", "ANTHEM"],
    "DXCM":  ["DEXCOM"],
    "HUM":   ["HUMANA"],
    "CI":    ["CIGNA"],
    "A":     ["AGILENT"],
    "IDXX":  ["IDEXX"],
    "EW":    ["EDWARDS LIFESCIENCES"],
    "CVS":   ["CVS HEALTH"],
    "JPM":   ["JPMORGAN CHASE", "JP MORGAN"],
    "BAC":   ["BANK OF AMERICA"],
    "GS":    ["GOLDMAN SACHS"],
    "MS":    ["MORGAN STANLEY"],
    "BLK":   ["BLACKROCK"],
    "C":     ["CITIGROUP"],
    "CB":    ["CHUBB"],
    "SCHW":  ["CHARLES SCHWAB"],
    "SPGI":  ["S&P GLOBAL"],
    "MCO":   ["MOODY'S", "MOODYS"],
    "CME":   ["CME GROUP"],
    "ICE":   ["INTERCONTINENTAL EXCHANGE"],
    "PGR":   ["PROGRESSIVE"],
    "USB":   ["U.S. BANCORP", "US BANCORP"],
    "PRU":   ["PRUDENTIAL FINANCIAL"],
    "MET":   ["METLIFE"],
    "AFL":   ["AFLAC"],
    "TRV":   ["TRAVELERS"],
    "PNC":   ["PNC FINANCIAL"],
    "COF":   ["CAPITAL ONE"],
    "BK":    ["BANK OF NEW YORK", "BNY MELLON"],
    "PG":    ["PROCTER & GAMBLE", "PROCTER"],
    "KO":    ["COCA-COLA", "COCA COLA"],
    "PEP":   ["PEPSICO"],
    "WMT":   ["WALMART"],
    "COST":  ["COSTCO"],
    "PM":    ["PHILIP MORRIS"],
    "MCD":   ["MCDONALD'S", "MCDONALDS"],
    "SBUX":  ["STARBUCKS"],
    "KMB":   ["KIMBERLY-CLARK", "KIMBERLY CLARK"],
    "CL":    ["COLGATE"],
    "MDLZ":  ["MONDELEZ"],
    "GIS":   ["GENERAL MILLS"],
    "KR":    ["KROGER"],
    "YUM":   ["YUM! BRANDS", "YUM BRANDS"],
    "HSY":   ["HERSHEY"],
    "XOM":   ["EXXON MOBIL", "EXXONMOBIL"],
    "CVX":   ["CHEVRON"],
    "EOG":   ["EOG RESOURCES"],
    "COP":   ["CONOCOPHILLIPS"],
    "OXY":   ["OCCIDENTAL PETROLEUM", "OCCIDENTAL"],
    "DVN":   ["DEVON ENERGY"],
    "HAL":   ["HALLIBURTON"],
    "SLB":   ["SCHLUMBERGER", "SLB"],
    "PSX":   ["PHILLIPS 66"],
    "VLO":   ["VALERO ENERGY", "VALERO"],
    "MPC":   ["MARATHON PETROLEUM"],
    "WMB":   ["WILLIAMS COMPANIES"],
    "OKE":   ["ONEOK"],
    "KMI":   ["KINDER MORGAN"],
    "CAT":   ["CATERPILLAR"],
    "DE":    ["DEERE & COMPANY", "JOHN DEERE"],
    "GE":    ["GENERAL ELECTRIC"],
    "ETN":   ["EATON"],
    "HON":   ["HONEYWELL"],
    "ITW":   ["ILLINOIS TOOL WORKS"],
    "EMR":   ["EMERSON ELECTRIC"],
    "WM":    ["WASTE MANAGEMENT"],
    "MMM":   ["3M"],
    "RTX":   ["RTX CORP", "RAYTHEON"],
    "NOC":   ["NORTHROP GRUMMAN"],
    "LMT":   ["LOCKHEED MARTIN"],
    "LHX":   ["L3HARRIS", "L3 HARRIS"],
    "FDX":   ["FEDEX"],
    "UPS":   ["UNITED PARCEL SERVICE"],
    "CSX":   ["CSX CORP"],
    "UNP":   ["UNION PACIFIC"],
    "GD":    ["GENERAL DYNAMICS"],
    "ROK":   ["ROCKWELL AUTOMATION"],
    "CMI":   ["CUMMINS"],
    "SHW":   ["SHERWIN-WILLIAMS", "SHERWIN WILLIAMS"],
    "DOW":   ["DOW INC"],
    "DD":    ["DUPONT"],
    "LYB":   ["LYONDELLBASELL"],
    "ECL":   ["ECOLAB"],
    "FCX":   ["FREEPORT-MCMORAN", "FREEPORT MCMORAN"],
    "NEM":   ["NEWMONT"],
    "PPG":   ["PPG INDUSTRIES"],
    "NEE":   ["NEXTERA ENERGY"],
    "DUK":   ["DUKE ENERGY"],
    "SO":    ["SOUTHERN COMPANY", "SOUTHERN CO"],
    "D":     ["DOMINION ENERGY", "DOMINION"],
    "EXC":   ["EXELON"],
    "AEP":   ["AMERICAN ELECTRIC POWER"],
    "DTE":   ["DTE ENERGY"],
    "SRE":   ["SEMPRA ENERGY", "SEMPRA"],
    "PLD":   ["PROLOGIS"],
    "EQIX":  ["EQUINIX"],
    "AMT":   ["AMERICAN TOWER"],
    "CCI":   ["CROWN CASTLE"],
    "PSA":   ["PUBLIC STORAGE"],
    "EQR":   ["EQUITY RESIDENTIAL"],
    "AVB":   ["AVALONBAY"],
    "TSM":   ["TAIWAN SEMICONDUCTOR", "TSMC"],
}


# ---------------------------------------------------------------------------
# Bloomberg V2 score (identico alla produzione)
# ---------------------------------------------------------------------------

def bloomberg_enhanced_score(ind: dict, inst_bonus: float = 0.0) -> float:
    base   = score_stock(ind)
    rsi    = ind.get("rsi_14") or 0
    vol    = ind.get("volume_ratio") or 0
    change = ind.get("weekly_change_pct") or 0
    sma50  = ind.get("above_sma50") or False

    bonus = 0.0
    if vol >= 1.5:       bonus += 2.0
    elif vol >= 1.2:     bonus += 0.5
    if 50 <= rsi <= 62:  bonus += 1.5
    elif 48 <= rsi < 50: bonus += 0.5
    elif rsi > 65:       bonus -= 2.0
    if change >= 2.0:    bonus += 1.5
    elif change >= 1.0:  bonus += 0.5
    if sma50:            bonus += 1.0

    return base + bonus + inst_bonus


# ---------------------------------------------------------------------------
# Fetch 13F filings da SEC EDGAR
# ---------------------------------------------------------------------------

def _sec_get(url: str, retries: int = 3) -> dict | None:
    """GET request a SEC EDGAR con retry e rate limit."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=SEC_HEADERS, timeout=20)
            if r.status_code == 200:
                return r
            elif r.status_code == 429:
                print(f"    [rate limit] aspetto 10s...")
                time.sleep(10)
            else:
                time.sleep(1)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
    return None


def _filing_date_to_quarter(filing_date: datetime) -> str:
    """
    Mappa una filing date 13F al trimestre che copre.
    13F depositato ~45gg dopo fine trimestre:
      Feb → Q4 anno precedente
      May → Q1 anno corrente
      Aug → Q2 anno corrente
      Nov → Q3 anno corrente
    """
    quarter_approx = filing_date - timedelta(days=50)
    m = quarter_approx.month
    y = quarter_approx.year
    if m <= 3:   return f"{y}-Q1"
    elif m <= 6: return f"{y}-Q2"
    elif m <= 9: return f"{y}-Q3"
    else:        return f"{y}-Q4"


def _quarter_to_end_date(q: str) -> datetime:
    """Converte '2024-Q4' in datetime(2024,12,31) ecc."""
    year, qnum = q.split("-Q")
    ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    m, d = ends[int(qnum)]
    return datetime(int(year), m, d)


def get_institution_13f_filings(cik: str, start_year: int = 2019) -> pd.DataFrame:
    """
    Recupera la lista di 13F-HR filings per una istituzione (incluse pagine storiche).
    Restituisce DataFrame con colonne: accessionNumber, filingDate
    """
    cik_padded = cik.zfill(10)
    main_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    r = _sec_get(main_url)
    if r is None:
        return pd.DataFrame()

    try:
        data = r.json()
    except Exception:
        return pd.DataFrame()

    rows = []

    def _extract_13f(forms, dates, accs):
        for form, date, acc in zip(forms, dates, accs):
            if form == "13F-HR":
                try:
                    d = datetime.strptime(date, "%Y-%m-%d")
                    if d.year >= start_year:
                        rows.append({"accessionNumber": acc, "filingDate": d})
                except Exception:
                    pass

    # Recent filings
    recent = data.get("filings", {}).get("recent", {})
    _extract_13f(
        recent.get("form", []),
        recent.get("filingDate", []),
        recent.get("accessionNumber", [])
    )

    # Pagine storiche (CIK{cik}-submissions-00N.json)
    for page_info in data.get("filings", {}).get("files", []):
        page_name = page_info.get("name", "")
        # Salta se fuori dal range di interesse
        filing_from = page_info.get("filingFrom", "9999-01-01")
        if filing_from[:4].isdigit() and int(filing_from[:4]) < start_year - 1:
            continue   # Tutti i filing in questa pagina sono troppo vecchi

        page_url = f"https://data.sec.gov/submissions/{page_name}"
        r2 = _sec_get(page_url)
        if r2 is None:
            continue
        try:
            d2 = r2.json()
            _extract_13f(
                d2.get("form", []),
                d2.get("filingDate", []),
                d2.get("accessionNumber", [])
            )
        except Exception:
            pass
        time.sleep(0.1)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.drop_duplicates("accessionNumber").sort_values("filingDate").reset_index(drop=True)

    # De-duplica per quarter: tieni solo il filing PIÙ RECENTE per ogni quarter.
    # Questo evita di scaricare decine di emendamenti o sub-entity filing per lo stesso trimestre.
    df["quarter"] = df["filingDate"].apply(_filing_date_to_quarter)
    df = df.sort_values("filingDate").groupby("quarter", as_index=False).last()
    df = df.sort_values("filingDate").reset_index(drop=True)
    return df[["accessionNumber", "filingDate", "quarter"]]


def parse_13f_names(xml_text: str) -> set:
    """
    Estrae issuer names dall'XML 13F infotable.
    Decodifica HTML entities (&amp; → &) e restituisce set uppercase.
    """
    # Supporta sia <nameOfIssuer> sia <ns1:nameOfIssuer> (namespace prefix usato da molti hedge fund)
    matches = re.findall(r'<(?:\w+:)?nameOfIssuer>([^<]+)</(?:\w+:)?nameOfIssuer>', xml_text, re.IGNORECASE)
    names = set()
    for m in matches:
        decoded = html.unescape(m.strip()).upper()
        names.add(decoded)
    return names


def get_13f_holdings_names(cik: str, accession: str, q_key: str) -> set:
    """
    Scarica e parsa un filing 13F-HR, restituisce set di nomi emittenti (uppercase).

    Parametri:
      cik       — CIK dell'istituzione (con o senza leading zeros)
      accession — accession number SEC (formato XXXXXXXXXX-YY-ZZZZZZ)
      q_key     — chiave trimestre ("2024-Q4") per costruire URL diretti

    Strategia (in ordine di velocità):
    1. URL diretto con pattern "{cik_padded}_{quarter_end}.xml"
    2. URL comuni (XML_Infotable.xml, infotable.xml, ...)
    3. Fallback: index.htm (30s timeout, skip se timeout)
    """
    cik_int    = str(int(cik))
    cik_padded = cik.zfill(10)
    acc_nodash = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/"

    # Quarter end date dal q_key (es: "2024-Q4" → "20241231")
    qe = _quarter_to_end_date(q_key)
    q_end_str = qe.strftime("%Y%m%d")

    # AllianceBernstein: naming XML varia per quarter — costruiamo pattern dinamici
    # Osservati: ABInfoTable.xml, ABSubmissionInfoTable.xml, Q1ABInfoTable.xml,
    #            Q224ABInfoTable.xml (Q + N + 2-digit-year)
    q_num = q_key.split("-Q")[1]           # "1","2","3","4"
    q_yy  = q_key.split("-Q")[0][-2:]     # ultimi 2 cifre anno
    ab_dynamic = f"Q{q_num}{q_yy}ABInfoTable.xml"  # es: "Q224ABInfoTable.xml"
    ab_simple  = f"Q{q_num}ABInfoTable.xml"         # es: "Q2ABInfoTable.xml"

    # ---- Pattern 1: file con nome che include CIK e data ----
    candidate_names = [
        f"13F_{cik_padded}_{q_end_str}.xml",   # Vanguard, MFS style
        "XML_Infotable.xml",                    # State Street style
        "xml_infotable.xml",
        "form13fInfoTable.xml",
        "form13finfotable.xml",
        "infotable.xml",
        "InformationTable.xml",
        "informationtable.xml",
        # AllianceBernstein variants
        "ABInfoTable.xml",
        "ABSubmissionInfoTable.xml",
        ab_dynamic,    # es: "Q224ABInfoTable.xml"
        ab_simple,     # es: "Q2ABInfoTable.xml"
    ]

    for fname in candidate_names:
        # Timeout breve (6s): se il file esiste risponde subito; se 404 risponde subito.
        # Se lento (server overload), lascia perdere e passa al prossimo.
        try:
            r = requests.get(base + fname, headers=SEC_HEADERS, timeout=6)
            if r.status_code == 200 and len(r.content) > 5_000:
                names = parse_13f_names(r.text)
                if len(names) > 50:
                    time.sleep(0.08)
                    return names
        except Exception:
            pass
        time.sleep(0.04)

    # ---- Fallback: index.htm (30s timeout, non bloccante) ----
    idx_url = f"{base}{accession}-index.htm"
    r_idx = None
    try:
        r_idx = requests.get(idx_url, headers=SEC_HEADERS, timeout=35)
        if r_idx.status_code != 200:
            r_idx = None
    except Exception:
        r_idx = None

    if r_idx is None:
        return set()

    # Trova link XML che NON siano nella cartella xslForm (quella è il viewer HTML)
    all_links = re.findall(
        r'href="(/Archives/edgar/data/[^"]+\.xml)"', r_idx.text, re.IGNORECASE
    )
    xml_url = None
    for link in all_links:
        lower = link.lower()
        if "xsl" not in lower and "primary_doc" not in lower:
            xml_url = "https://www.sec.gov" + link
            break

    if xml_url is None:
        return set()

    r2 = _sec_get(xml_url)
    if r2 is None:
        return set()

    time.sleep(0.08)
    return parse_13f_names(r2.text)


# ---------------------------------------------------------------------------
# Build quarterly institutional holdings table
# ---------------------------------------------------------------------------

def build_institutional_table(tickers: list) -> pd.DataFrame:
    """
    Scarica 13F da tutte le istituzioni e costruisce una tabella
    quarter_end × ticker → (n_holders, n_increasing)

    Restituisce DataFrame con colonne:
      quarter_end | ticker | n_holders | n_holders_prev | delta_holders | inst_score
    """
    # Verifica cache
    if os.path.exists(CACHE_13F):
        age_days = (datetime.now().timestamp() - os.path.getmtime(CACHE_13F)) / 86400
        if age_days < 90:  # Cache valida per 90 giorni
            with open(CACHE_13F, "rb") as f:
                data = pickle.load(f)
            print(f"  Cache 13F: {len(data)} record ({age_days:.0f}gg fa)")
            return data

    print(f"\nScaricamento 13F da SEC EDGAR per {len(TOP_INSTITUTIONS)} istituzioni...")
    print("  (prima esecuzione: 20-40 minuti, risultato cached per 90 giorni)\n")

    # Step 1: per ogni istituzione, per ogni filing trimestrale, ottieni i nomi degli emittenti
    # Struttura: {(institution, quarter_end_str): set_of_issuer_names}
    inst_quarters: dict = {}

    for inst_name, cik in TOP_INSTITUTIONS.items():
        print(f"\n  [{inst_name}] CIK={cik}")
        filings = get_institution_13f_filings(cik)
        if filings.empty:
            print(f"    WARN: nessun filing trovato")
            continue

        # Filtra 2019-2026 (la de-dup per quarter è già fatta in get_institution_13f_filings)
        filings = filings[filings["filingDate"].dt.year >= 2019].copy()
        print(f"    Filing trimestrali trovati 2019+: {len(filings)}")

        for _, row in filings.iterrows():
            filing_date = row["filingDate"]
            acc         = row["accessionNumber"]
            q_key       = row.get("quarter") or _filing_date_to_quarter(filing_date)

            print(f"    {filing_date.date()} -> {q_key} [{acc[:20]}...]", end="", flush=True)
            names = get_13f_holdings_names(cik, acc, q_key)
            if names:
                inst_quarters[(inst_name, q_key)] = names
                print(f" -> {len(names)} emittenti")
            else:
                print(" -> [vuoto]")

            time.sleep(0.2)

    if not inst_quarters:
        print("ERRORE: nessun dato 13F scaricato")
        return pd.DataFrame()

    # Step 2: per ogni (quarter, ticker) conta quante istituzioni detengono la posizione
    print("\n\nElaborazione coverage istituzionale per ticker...")

    # Ottieni tutti i quarter unici (ordinati)
    all_quarters = sorted(set(q for (_, q) in inst_quarters.keys()))

    # Per ogni ticker: keyword list per il matching
    results = []
    for quarter in all_quarters:
        for ticker in tickers:
            keywords = TICKER_NAME_KEYWORDS.get(ticker, [ticker])
            count = 0
            for inst_name in TOP_INSTITUTIONS:
                holdings = inst_quarters.get((inst_name, quarter), set())
                # Match: almeno una keyword trovata nel nome emittente
                matched = any(
                    any(kw in issuer for issuer in holdings)
                    for kw in keywords
                )
                if matched:
                    count += 1
            results.append({
                "quarter": quarter,
                "ticker": ticker,
                "n_holders": count,
            })

    df = pd.DataFrame(results)

    # Step 3: calcola delta QoQ
    df = df.sort_values(["ticker", "quarter"]).reset_index(drop=True)
    df["n_holders_prev"] = df.groupby("ticker")["n_holders"].shift(1)
    df["delta_holders"]  = df["n_holders"] - df["n_holders_prev"]

    # Step 4: calcola inst_score per (quarter, ticker)
    def _score(row):
        d = row["delta_holders"]
        if pd.isna(d):
            return 0.0
        if d >= 4:
            return INST_BONUS_STRONG
        elif d >= 2:
            return INST_BONUS_MEDIUM
        elif d >= 1 and row["n_holders"] > 0:
            # Controlla anche incremento relativo
            prev = row["n_holders_prev"] or 0
            pct = (d / prev * 100) if prev > 0 else 100
            if pct >= 10:
                return INST_BONUS_WEAK
        return 0.0

    df["inst_score"] = df.apply(_score, axis=1)

    df["quarter_end"] = df["quarter"].apply(_quarter_to_end_date)
    # Data disponibile al mercato: fine trimestre + lag (50 giorni)
    df["available_from"] = df["quarter_end"] + timedelta(days=FILING_LAG_DAYS)

    # Salva cache
    with open(CACHE_13F, "wb") as f:
        pickle.dump(df, f)
    print(f"\nCache 13F salvata: {CACHE_13F}")
    print(f"Ticker con coverage > 0 in almeno un quarter: "
          f"{df[df['n_holders'] > 0]['ticker'].nunique()}")

    return df


# ---------------------------------------------------------------------------
# Lookup inst_score per data e ticker
# ---------------------------------------------------------------------------

def get_inst_score(ticker: str, signal_date, inst_df: pd.DataFrame) -> float:
    """
    Restituisce il bonus inst_score per ticker a una signal_date.
    Usa il dato 13F più recente disponibile (rispetta lag di 50gg).
    """
    if inst_df.empty:
        return 0.0

    mask = (
        (inst_df["ticker"] == ticker) &
        (inst_df["available_from"] <= signal_date)
    )
    available = inst_df[mask]
    if available.empty:
        return 0.0

    # Prendi il trimestre più recente disponibile
    latest = available.sort_values("quarter_end").iloc[-1]
    return float(latest["inst_score"])


# ---------------------------------------------------------------------------
# Selezione candidati
# ---------------------------------------------------------------------------

def get_top_candidates(all_data: dict, sig_date, top_n: int,
                       inst_df: pd.DataFrame, use_inst: bool) -> list:
    candidates = []
    for ticker, df in all_data.items():
        hist = df[df.index <= sig_date].tail(200)
        if len(hist) < MIN_BARS:
            continue
        try:
            ind   = compute_indicators(hist)
            score = score_stock(ind)
            if not (score > 0 and (ind.get("macd_hist") or 0) > 0):
                continue
            candidates.append((ticker, ind, score))
        except Exception:
            continue

    candidates.sort(key=lambda x: x[2], reverse=True)
    top20 = candidates[:PRE_FILTER_N]

    if use_inst:
        final = sorted(
            top20,
            key=lambda x: bloomberg_enhanced_score(
                x[1],
                inst_bonus=get_inst_score(x[0], sig_date, inst_df)
            ),
            reverse=True
        )
    else:
        final = sorted(top20, key=lambda x: bloomberg_enhanced_score(x[1]), reverse=True)

    return final[:top_n]


# ---------------------------------------------------------------------------
# Simulazione trade
# ---------------------------------------------------------------------------

def simulate_trade(future, entry, sl, tp):
    for i, (_, row) in enumerate(future.iterrows()):
        if i >= SAFETY_CAP:
            return "TIMEOUT", float(future["Close"].iloc[i - 1]), i
        if float(row["Low"]) <= sl:
            return "LOSS", sl, i + 1
        if float(row["High"]) >= tp:
            return "WIN", tp, i + 1
    n = len(future)
    return ("OPEN", float(future["Close"].iloc[-1]), n) if n else ("OPEN", entry, 0)


def process_signal(ticker, ind, all_data, sig_date):
    entry = ind["price"]
    atr   = ind.get("atr_14") or (entry * 0.02)
    sl    = round(entry - SL_MULT * atr, 4)
    tp    = round(entry + RR * SL_MULT * atr, 4)

    future = all_data[ticker][all_data[ticker].index > sig_date]
    if future.empty:
        return None

    outcome, exit_price, bars = simulate_trade(future, entry, sl, tp)
    pnl_pct  = (exit_price - entry) / entry * 100
    comm_pct = COMMISSION_EUR / TRADE_SIZE * 100 if outcome != "OPEN" else 0.0

    return {
        "date":      sig_date.strftime("%Y-%m-%d"),
        "year":      sig_date.year,
        "ticker":    ticker,
        "outcome":   outcome,
        "bars_held": bars,
        "pnl_pct":   round(pnl_pct - comm_pct, 4),
    }


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def run_backtest(all_data: dict, inst_df: pd.DataFrame, use_inst: bool,
                 top_n: int = TOP_N, label: str = "") -> pd.DataFrame:
    signal_dates = pd.date_range(BT_START, BT_END, freq="W-FRI")
    trades = []
    for sig_date in signal_dates:
        top = get_top_candidates(all_data, sig_date, top_n, inst_df, use_inst)
        for ticker, ind, _ in top:
            rec = process_signal(ticker, ind, all_data, sig_date)
            if rec:
                trades.append(rec)
    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Statistiche
# ---------------------------------------------------------------------------

def compute_stats(df: pd.DataFrame, label: str) -> dict:
    closed = df[df["outcome"].isin(["WIN", "LOSS", "TIMEOUT"])].copy()
    if closed.empty:
        return None

    wins     = closed[closed["outcome"] == "WIN"]
    losses   = closed[closed["outcome"] == "LOSS"]
    timeouts = closed[closed["outcome"] == "TIMEOUT"]

    wr      = len(wins) / len(closed) * 100
    avg_win = wins["pnl_pct"].mean()   if not wins.empty   else 0
    avg_los = losses["pnl_pct"].mean() if not losses.empty else 0
    ev_pct  = (wr / 100) * avg_win + (1 - wr / 100) * avg_los

    total_pnl  = (closed["pnl_pct"] / 100 * TRADE_SIZE).sum()
    net_profit = total_pnl - max(0, total_pnl * 0.26)
    ann_net    = net_profit / 6.33

    balance  = CAPITAL
    balances = []
    for _, row in closed.sort_values("date").iterrows():
        balance += row["pnl_pct"] / 100 * TRADE_SIZE
        balances.append(balance)
    bal_arr = np.array(balances) if balances else np.array([CAPITAL])
    peak    = np.maximum.accumulate(bal_arr)
    max_dd  = ((bal_arr - peak) / peak * 100).min()

    max_cl = curr = 0
    for _, row in closed.sort_values("date").iterrows():
        if row["outcome"] == "LOSS":
            curr += 1; max_cl = max(max_cl, curr)
        else:
            curr = 0

    yearly = {}
    for _, row in closed.sort_values("date").iterrows():
        yr = int(row["year"])
        yearly[yr] = yearly.get(yr, 0) + row["pnl_pct"] / 100 * TRADE_SIZE

    return {
        "label":        label,
        "trades":       len(closed),
        "wins":         len(wins),
        "losses":       len(losses),
        "timeouts":     len(timeouts),
        "win_rate":     round(wr, 1),
        "avg_win":      round(avg_win, 2),
        "avg_loss":     round(avg_los, 2),
        "ev_pct":       round(ev_pct, 3),
        "ev_eur":       round(ev_pct / 100 * TRADE_SIZE, 2),
        "ann_net_eur":  round(ann_net, 0),
        "ann_pct":      round(ann_net / CAPITAL * 100, 1),
        "max_dd":       round(max_dd, 1),
        "max_consec_l": max_cl,
        "avg_bars":     round(closed["bars_held"].mean(), 1),
        "yearly":       yearly,
        "pnl_series":   closed["pnl_pct"].values,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SEP  = "=" * 96
    SEP2 = "-" * 92

    print(SEP)
    print("  BLOOMBERG V2  vs  BLOOMBERG V2 + 13F INSTITUTIONAL SIGNAL")
    print(f"  SL={SL_MULT}xATR  R:R 1:{int(RR)}  |  Top {TOP_N}/sett.  |  2020-2026 (6.33 anni)")
    inst_names = ", ".join(TOP_INSTITUTIONS.keys())
    print(f"  Istituzioni ({len(TOP_INSTITUTIONS)}): {inst_names}  |  Filing lag: {FILING_LAG_DAYS}gg")
    print(SEP)

    # Carica price data
    print("\nCaricamento price data...")
    with open(CACHE_PRICE, "rb") as f:
        all_data = pickle.load(f)

    usa_data = {t: df for t, df in all_data.items() if t in WATCHLIST_USA}
    print(f"Ticker USA disponibili nel cache: {len(usa_data)}")

    # Scarica/carica dati 13F
    print("\nCaricamento dati 13F istituzionali...")
    inst_df = build_institutional_table(WATCHLIST_USA)

    if not inst_df.empty:
        n_tickers_with_data = inst_df[inst_df["n_holders"] > 0]["ticker"].nunique()
        n_quarters = inst_df["quarter"].nunique()
        total_with_signal = inst_df[inst_df["inst_score"] > 0]

        print(f"\n  Summary dati 13F:")
        print(f"  Trimestri coperti:         {n_quarters}")
        print(f"  Ticker con holders > 0:    {n_tickers_with_data}/{len(WATCHLIST_USA)}")
        print(f"  Segnali positivi totali:   {len(total_with_signal)}")

        if not total_with_signal.empty:
            print(f"\n  Top ticker per inst_score medio:")
            top_by_score = (inst_df.groupby("ticker")["inst_score"].mean()
                                   .sort_values(ascending=False).head(10))
            for t, s in top_by_score.items():
                avg_h = inst_df[inst_df["ticker"] == t]["n_holders"].mean()
                print(f"    {t:8s} avg_score={s:.2f}  avg_holders={avg_h:.1f}")

    # Backtest
    print(f"\n[1/2] Bloomberg V2 PURO (senza 13F)...")
    df_base = run_backtest(usa_data, inst_df, use_inst=False)
    s_base  = compute_stats(df_base, f"Bloomberg V2 Puro        (Top {TOP_N})")

    print(f"[2/2] Bloomberg V2 + 13F INST (con bonus istituzionale)...")
    df_inst = run_backtest(usa_data, inst_df, use_inst=True)
    s_inst  = compute_stats(df_inst, f"Bloomberg V2 + 13F Inst  (Top {TOP_N})")

    # Tabella comparativa
    print(f"\n\n{SEP}")
    print("  RISULTATI COMPARATIVI")
    print(SEP)
    hdr = (f"  {'Strategia':<28} {'Trade':>6} {'WR%':>6} {'AvgWIN':>8} {'AvgLSS':>8} "
           f"{'EV EUR':>8} {'AnnNet':>9} {'Ann%':>6} {'MaxDD':>7} {'MaxSL-':>7} {'AvgWks':>7}")
    print(hdr)
    print(f"  {SEP2}")

    for s in [s_base, s_inst]:
        if not s:
            print("  [nessun dato]")
            continue
        marker = "  <-- 13F" if "13F" in s["label"] else ""
        print(
            f"  {s['label']:<28} "
            f"{s['trades']:>6} "
            f"{s['win_rate']:>5.1f}% "
            f"{s['avg_win']:>+7.1f}% "
            f"{s['avg_loss']:>+7.1f}% "
            f"{s['ev_eur']:>+8.2f} "
            f"{s['ann_net_eur']:>+8.0f}E "
            f"{s['ann_pct']:>+5.1f}% "
            f"{s['max_dd']:>+6.1f}% "
            f"{s['max_consec_l']:>7} "
            f"{s['avg_bars']:>7.1f}"
            f"{marker}"
        )

    print(f"  {SEP2}")
    print(SEP)

    # Dettaglio annuale
    if s_base and s_inst:
        print(f"\n  Anno-per-anno: PURO vs 13F INST")
        print(f"  {'Anno':<6} {'Puro lordo':>12} {'13F lordo':>12} {'Delta':>8}")
        print(f"  {'-'*44}")
        all_years = sorted(set(list(s_base["yearly"].keys()) + list(s_inst["yearly"].keys())))
        for yr in all_years:
            g_base = s_base["yearly"].get(yr, 0)
            g_inst = s_inst["yearly"].get(yr, 0)
            delta  = g_inst - g_base
            marker = " +" if delta > 50 else (" -" if delta < -50 else "  ")
            print(f"  {yr:<6} {g_base:>+11.0f}E {g_inst:>+11.0f}E {delta:>+7.0f}E{marker}")

    print(f"\n{SEP}")
    print("  DISTRIBUZIONE PnL% per trade")
    print(f"  {'-'*72}")
    for s in [s_base, s_inst]:
        if not s:
            continue
        p = s["pnl_series"]
        print(f"  {s['label'][:28]:<28} "
              f"P10={np.percentile(p,10):+5.1f}%  "
              f"Med={np.percentile(p,50):+5.1f}%  "
              f"P90={np.percentile(p,90):+5.1f}%  "
              f"Std={p.std():5.2f}%")
    print(SEP)

    # Salva
    if not df_base.empty:
        df_base.to_csv(
            os.path.join(os.path.dirname(__file__), "backtest_13f_base_trades.csv"),
            index=False)
    if not df_inst.empty:
        df_inst.to_csv(
            os.path.join(os.path.dirname(__file__), "backtest_13f_signal_trades.csv"),
            index=False)

    print("\nRisultati salvati:")
    print("  backtest_13f_base_trades.csv")
    print("  backtest_13f_signal_trades.csv")
    print(SEP)
