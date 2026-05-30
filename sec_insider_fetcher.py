# sec_insider_fetcher.py  (v4 - submissions API + parallel XML)
#
# Step 1: Per ogni company, chiama data.sec.gov/submissions/CIK{cik}.json
#         -> ottieni Form 4 con primaryDocument (filename corretto, zero 404)
# Step 2: Download e parsing Form 4 XML in parallelo (8 worker, 9 req/s)
#
# Stima: ~15-20 min per 2022->oggi
# Output: sec_cache/insider_transactions.csv

import requests
import time
import os
import json
import xml.etree.ElementTree as ET
import pandas as pd
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR   = r"C:\Users\corr8\Desktop\obsidian-vault\Stock Market Bot\sec_cache"
OUTPUT_CSV  = os.path.join(CACHE_DIR, "insider_transactions.csv")
CIK_CACHE   = os.path.join(CACHE_DIR, "cik_map.json")
HEADERS     = {"User-Agent": "StockMarketBot corradocuri@gmail.com"}
START_DATE  = "2022-01-01"   # filtro data minima
MAX_WORKERS = 8
MAX_RPS     = 9.0            # sotto il limite SEC di 10 req/sec

US_TICKERS = [
    "AAPL","MSFT","NVDA","GOOGL","GOOG","META","AMZN","TSLA","AVGO",
    "AMD","QCOM","TXN","ADI","MU","AMAT","KLAC","SNPS","CDNS","NXPI","MRVL","INTC",
    "CRM","ADBE","NOW","PANW","INTU","ORCL","IBM","CSCO","FTNT",
    "DDOG","SNOW","OKTA","ZM","TWLO","DOCU","WDAY",
    "NFLX","DIS","SPOT","SHOP","MELI","BKNG","EBAY","UBER","TTD","SNAP","PINS","ROKU",
    "V","MA","PYPL","AXP",
    "LLY","ABBV","MRK","ABT","AMGN","GILD","VRTX","REGN","BMY","PFE","JNJ","MRNA",
    "BIIB","ILMN","UNH","TMO","DHR","ISRG","MDT","BSX","BDX","SYK","ELV","HUM","CI",
    "IDXX","DXCM","EW","CVS","A",
    "JPM","BAC","GS","MS","BLK","C","CB","SCHW","SPGI","MCO","CME","ICE","USB",
    "PGR","PRU","MET","AFL","TRV","PNC","COF","BK",
    "PG","KO","PEP","WMT","COST","PM","MCD","SBUX","KMB","CL","MDLZ","GIS","KR",
    "YUM","HSY","HD","LOW","TJX","NKE","RACE","MAR","HLT","EA","TTWO",
    "XOM","CVX","EOG","COP","OXY","DVN","HAL","SLB","VLO","MPC","PSX","WMB","OKE","KMI",
    "CAT","DE","GE","ETN","HON","ITW","EMR","WM","MMM","RTX","NOC","LMT","LHX",
    "FDX","UPS","CSX","UNP","GD","ROK","CMI",
    "SHW","DOW","DD","LYB","ECL","FCX","NEM","PPG",
    "NEE","DUK","SO","D","EXC","AEP","DTE","SRE",
    "PLD","EQIX","AMT","CCI","PSA","EQR","AVB","TSM",
]


# ── Rate limiter (thread-safe, token bucket) ──────────────────────────────────
class RateLimiter:
    def __init__(self, max_rps):
        self._interval = 1.0 / max_rps
        self._lock     = threading.Lock()
        self._last     = 0.0

    def wait(self):
        with self._lock:
            now  = time.monotonic()
            wait = self._last + self._interval - now
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

_rl = RateLimiter(MAX_RPS)
_tl = threading.local()   # sessione per thread


def get_session():
    if not hasattr(_tl, "session"):
        s = requests.Session()
        s.headers.update(HEADERS)
        _tl.session = s
    return _tl.session


# ── Step 1: submissions API ───────────────────────────────────────────────────

def extract_form4s(filings_block, ticker, cik_int, start_date):
    """Estrae Form 4 da un blocco 'filings' del submissions JSON."""
    forms    = filings_block.get("form",            [])
    dates    = filings_block.get("filingDate",      [])
    accs     = filings_block.get("accessionNumber", [])
    docs     = filings_block.get("primaryDocument", [])
    results  = []
    for i, form in enumerate(forms):
        if form != "4":
            continue
        date = dates[i] if i < len(dates) else ""
        if date < start_date:
            continue
        acc = accs[i].replace("-", "") if i < len(accs) else ""
        doc = docs[i] if i < len(docs) else ""
        if not acc or not doc:
            continue
        results.append({
            "ticker":     ticker,
            "cik_int":    cik_int,
            "filed_date": date,
            "accession":  acc,
            "primary_doc": doc,
        })
    return results


def get_company_form4s(ticker, cik_str, start_date):
    """Ritorna lista di Form 4 per una company dal 2022 in poi."""
    session = get_session()
    cik_int = int(cik_str)

    url = f"https://data.sec.gov/submissions/CIK{cik_str}.json"
    try:
        _rl.wait()
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    filings_section = data.get("filings", {})
    recent  = filings_section.get("recent", {})
    results = extract_form4s(recent, ticker, cik_int, start_date)

    # Se il blocco 'recent' non va abbastanza indietro, scarica le pagine extra
    recent_dates = recent.get("filingDate", [])
    if recent_dates and min(recent_dates) > start_date:
        for file_info in filings_section.get("files", []):
            fname = file_info.get("name", "")
            if not fname:
                continue
            try:
                _rl.wait()
                r2 = session.get(f"https://data.sec.gov/submissions/{fname}", timeout=30)
                if r2.status_code != 200:
                    continue
                page = r2.json()
                results.extend(extract_form4s(page, ticker, cik_int, start_date))
                page_dates = page.get("filingDate", [])
                if page_dates and min(page_dates) <= start_date:
                    break   # siamo andati abbastanza indietro
            except Exception:
                continue

    return results


# ── Step 2: parsing XML (usato dai worker thread) ─────────────────────────────

def parse_one_filing(filing):
    session  = get_session()
    cik_int  = filing["cik_int"]
    acc      = filing["accession"]
    doc      = filing["primary_doc"]

    # Rimuovi prefix XSLT se presente (es. "xslF345X06/form4.xml" -> "form4.xml")
    doc_clean = doc.split("/")[-1]
    xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{doc_clean}"

    try:
        _rl.wait()
        resp = session.get(xml_url, timeout=20)
        if resp.status_code != 200:
            return filing, []
        root = ET.fromstring(resp.content)
    except Exception:
        return filing, []

    # Ruolo dell'insider
    role = "OTHER"
    for rel in root.findall(".//reportingOwnerRelationship"):
        title       = rel.findtext("officerTitle", "").upper()
        is_officer  = rel.findtext("isOfficer",  "0") == "1"
        is_director = rel.findtext("isDirector", "0") == "1"
        if any(k in title for k in ["CEO", "CHIEF EXECUTIVE"]):
            role = "CEO"; break
        elif any(k in title for k in ["CFO", "CHIEF FINANCIAL"]):
            role = "CFO"; break
        elif "PRESIDENT" in title:
            role = "PRESIDENT"; break
        elif is_officer:
            role = "OFFICER"
        elif is_director and role not in ("OFFICER",):
            role = "DIRECTOR"

    transactions = []
    for txn in root.findall(".//nonDerivativeTransaction"):
        try:
            txn_date = txn.findtext(".//transactionDate/value", "")
            txn_code = txn.findtext(".//transactionCoding/transactionCode", "")
            shares   = float(txn.findtext(".//transactionShares/value",        "0") or 0)
            price    = float(txn.findtext(".//transactionPricePerShare/value", "0") or 0)
            is_om    = txn_code in ("P", "S")
            if txn_date and txn_code:
                transactions.append({
                    "transaction_date": txn_date,
                    "role":             role,
                    "transaction_code": txn_code,
                    "shares":           shares,
                    "price_per_share":  price,
                    "is_open_market":   is_om,
                })
        except Exception:
            continue

    return filing, transactions


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(CACHE_DIR, exist_ok=True)

    with open(CIK_CACHE) as f:
        cik_map = json.load(f)

    valid_tickers = [t for t in US_TICKERS if t in cik_map]
    print(f"SEC EDGAR Insider Fetcher v4 -- {len(valid_tickers)} ticker USA")
    print(f"Periodo: {START_DATE} -> oggi | Workers: {MAX_WORKERS} | Rate: {MAX_RPS} req/s\n")

    # ── Step 1: submissions API (186 richieste, ~30 sec) ─────────────────────
    print(f"Step 1: recupero Form 4 via submissions API ({len(valid_tickers)} company)...")
    all_filings = []
    for i, ticker in enumerate(valid_tickers, 1):
        cik = cik_map[ticker]
        filings = get_company_form4s(ticker, cik, START_DATE)
        all_filings.extend(filings)
        if i % 20 == 0 or i == len(valid_tickers):
            print(f"\r  {i}/{len(valid_tickers)} company | Form 4 trovati: {len(all_filings):,}", end="", flush=True)

    print(f"\n  Totale Form 4: {len(all_filings):,} (dal {START_DATE})")

    # ── Step 2: download XML in parallelo ────────────────────────────────────
    total = len(all_filings)
    print(f"\nStep 2: parsing {total:,} Form 4 XML in parallelo ({MAX_WORKERS} workers)...")
    t0       = time.monotonic()
    all_rows = []
    errors   = 0
    done     = 0
    lock     = threading.Lock()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(parse_one_filing, f): f for f in all_filings}
        for future in as_completed(futures):
            filing, txns = future.result()
            with lock:
                done += 1
                if not txns:
                    errors += 1
                for t in txns:
                    all_rows.append({
                        "ticker":           filing["ticker"],
                        "filed_date":       filing["filed_date"],
                        "transaction_date": t["transaction_date"],
                        "role":             t["role"],
                        "transaction_code": t["transaction_code"],
                        "shares":           t["shares"],
                        "price_per_share":  t["price_per_share"],
                        "is_open_market":   t["is_open_market"],
                    })
                if done % 200 == 0 or done == total:
                    elapsed = time.monotonic() - t0
                    rps     = done / elapsed if elapsed > 0 else 0
                    eta_s   = (total - done) / rps if rps > 0 else 0
                    print(
                        f"\r  {done}/{total} ({done/total*100:.0f}%) | "
                        f"righe: {len(all_rows):,} | err: {errors} | "
                        f"{rps:.1f} req/s | ETA: {eta_s/60:.1f} min   ",
                        end="", flush=True
                    )

    elapsed_tot = time.monotonic() - t0
    print(f"\n  Completato in {elapsed_tot/60:.1f} min | "
          f"{len(all_rows):,} transazioni | errori XML: {errors}")

    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\nSalvato: {OUTPUT_CSV}")
        print(f"Totale righe:      {len(df):,}")
        print(f"Ticker con dati:   {df['ticker'].nunique()}")
        print(f"Range date:        {df['filed_date'].min()} -> {df['filed_date'].max()}")
        print(f"\nDistribuzione codici (open-market):")
        print(df[df['is_open_market']]['transaction_code'].value_counts().to_string())
        print(f"\nDistribuzione ruoli (open-market):")
        print(df[df['is_open_market']]['role'].value_counts().to_string())
    else:
        print("Nessun dato trovato.")
