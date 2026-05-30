import os
from dotenv import load_dotenv

# Usa sempre il .env nella stessa cartella di config.py, indipendente dal CWD
# (necessario quando Task Scheduler avvia gli script da una CWD diversa)
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_ENV_PATH, override=True)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Watchlist USA — universo backtest ottimale (186 titoli)
# Fonte: market_data.pkl — backtest Bloomberg V2 SL=2.0 RR=2.0 2020-2026
# Rimossi vs lista precedente: LRCX, CRWD, PLTR, ABNB, APD, WELL, WFC
# Aggiunti vs lista precedente: A, AEP, AFL, AVB, BK, BMY, CDNS, COF, CSX, CVS,
#   DD, DOCU, DTE, DVN, EQR, EW, GOOG, HSY, IDXX, ILMN, KMB, KMI, KR, LHX, LYB,
#   MET, MMM, NEM, OKE, OKTA, PNC, PPG, PRU, ROK, ROKU, SNAP, SNOW, SRE, TRV,
#   TTWO, TWLO, USB, WM, WMB
WATCHLIST_USA = [
    # Mega cap tech (9)
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AMZN", "TSLA", "AVGO",
    # Semiconduttori (12)
    "AMD", "QCOM", "TXN", "ADI", "MU", "AMAT", "KLAC", "SNPS",
    "NXPI", "MRVL", "INTC", "CDNS",
    # Software / Cloud / Cyber (16)
    "CRM", "ADBE", "NOW", "PANW", "INTU", "ORCL", "IBM", "CSCO",
    "FTNT", "DDOG", "ZM", "WDAY", "OKTA", "DOCU", "SNOW", "TWLO",
    # Internet / Media / E-comm (12)
    "NFLX", "DIS", "SPOT", "SHOP", "MELI", "BKNG", "EBAY",
    "UBER", "TTD", "SNAP", "PINS", "ROKU",
    # Consumer Cyclical (9)
    "HD", "LOW", "TJX", "NKE", "RACE", "MAR", "HLT", "EA", "TTWO",
    # Fintech / Pagamenti (4)
    "V", "MA", "PYPL", "AXP",
    # Healthcare - Pharma / Biotech (14)
    "LLY", "ABBV", "MRK", "ABT", "AMGN", "GILD",
    "VRTX", "REGN", "PFE", "JNJ", "MRNA", "BIIB", "BMY", "ILMN",
    # Healthcare - Dispositivi / Servizi (16)
    "UNH", "TMO", "DHR", "ISRG", "MDT", "BSX", "BDX", "SYK",
    "ELV", "DXCM", "HUM", "CI", "A", "IDXX", "EW", "CVS",
    # Financials (21)
    "JPM", "BAC", "GS", "MS", "BLK", "C", "CB", "SCHW",
    "SPGI", "MCO", "CME", "ICE", "PGR", "USB", "PRU", "MET",
    "AFL", "TRV", "PNC", "COF", "BK",
    # Consumer Defensive (15)
    "PG", "KO", "PEP", "WMT", "COST", "PM", "MCD", "SBUX",
    "KMB", "CL", "MDLZ", "GIS", "KR", "YUM", "HSY",
    # Energy (14)
    "XOM", "CVX", "EOG", "COP", "OXY", "DVN", "HAL",
    "SLB", "PSX", "VLO", "MPC", "WMB", "OKE", "KMI",
    # Industrials (20)
    "CAT", "DE", "GE", "ETN", "HON", "ITW", "EMR", "WM", "MMM",
    "RTX", "NOC", "LMT", "LHX", "FDX", "UPS", "CSX", "UNP", "GD", "ROK", "CMI",
    # Materials (8)
    "SHW", "DOW", "DD", "LYB", "ECL", "FCX", "NEM", "PPG",
    # Utilities (8)
    "NEE", "DUK", "SO", "D", "EXC", "AEP", "DTE", "SRE",
    # Real Estate (7)
    "PLD", "EQIX", "AMT", "CCI", "PSA", "EQR", "AVB",
    # Asia / global (1)
    "TSM",
]

# Watchlist Europa — universo backtest ottimale (61 titoli)
# Fonte: market_data.pkl — backtest Bloomberg V2 SL=2.0 RR=2.0 2020-2026
# Rimossi vs lista precedente: tutti i .MI (19 italiani), DTE.DE, HNR1.DE, MBG.DE,
#   PAH3.DE, 1COV.DE, ENR.DE, HFG.DE, DHER.DE, UNA.AS, ADYEN.AS,
#   CAP.PA, DSY.PA, EL.PA, SGO.PA, STM.PA, TEF.MC, FER.MC, AZN.L, ULVR.L, VOD.L
WATCHLIST_EUROPE = [
    # Germania (.DE) — 22
    "ADS.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE",
    "CON.DE", "DBK.DE", "DB1.DE", "EOAN.DE", "FRE.DE", "HEN3.DE",
    "IFX.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "RWE.DE", "SAP.DE",
    "SIE.DE", "SHL.DE", "VNA.DE", "VOW3.DE",
    # Paesi Bassi (.AS) — 10
    "AGN.AS", "ASM.AS", "ASML.AS", "HEIA.AS", "IMCD.AS", "NN.AS",
    "PHIA.AS", "RAND.AS", "AD.AS", "WKL.AS",
    # Francia (.PA) — 12
    "AI.PA", "AIR.PA", "BNP.PA", "GLE.PA", "KER.PA", "MC.PA",
    "OR.PA", "PUB.PA", "RMS.PA", "SAN.PA", "SU.PA", "TTE.PA",
    # Spagna (.MC) — 7
    "ACS.MC", "ANA.MC", "BBVA.MC", "IBE.MC", "ITX.MC", "REP.MC", "SAN.MC",
    # UK (.L) — 10
    "BARC.L", "BP.L", "GLEN.L", "GSK.L", "HSBA.L", "LLOY.L",
    "NWG.L", "RIO.L", "SHEL.L", "STAN.L",
]

# Nomi completi per messaggi Telegram (Trade Republic style)
TICKER_TO_NAME = {
    # USA - Mega cap tech
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA",
    "GOOGL": "Alphabet (A)", "GOOG": "Alphabet (C)", "META": "Meta Platforms", "AMZN": "Amazon",
    "TSLA": "Tesla", "AVGO": "Broadcom",
    # USA - Semiconduttori
    "AMD": "Advanced Micro Devices", "QCOM": "QUALCOMM", "TXN": "Texas Instruments",
    "ADI": "Analog Devices", "MU": "Micron Technology", "AMAT": "Applied Materials",
    "KLAC": "KLA", "SNPS": "Synopsys", "CDNS": "Cadence Design Systems",
    "NXPI": "NXP Semiconductors", "MRVL": "Marvell Technology", "INTC": "Intel",
    "LRCX": "Lam Research", "MCHP": "Microchip Technology", "ON": "ON Semiconductor",
    # USA - Software / Cloud / Cyber
    "CRM": "Salesforce", "ADBE": "Adobe", "NOW": "ServiceNow", "PANW": "Palo Alto Networks",
    "INTU": "Intuit", "ORCL": "Oracle", "IBM": "IBM", "CSCO": "Cisco Systems",
    "FTNT": "Fortinet", "DDOG": "Datadog", "SNOW": "Snowflake", "OKTA": "Okta",
    "ZM": "Zoom Video", "TWLO": "Twilio", "DOCU": "DocuSign", "WDAY": "Workday",
    "ZS": "Zscaler", "CRWD": "CrowdStrike", "NET": "Cloudflare",
    "MDB": "MongoDB", "PLTR": "Palantir",
    # USA - Internet / Media
    "NFLX": "Netflix", "DIS": "Walt Disney", "SPOT": "Spotify", "SHOP": "Shopify",
    "MELI": "MercadoLibre", "BKNG": "Booking Holdings", "EBAY": "eBay",
    "UBER": "Uber", "TTD": "The Trade Desk", "SNAP": "Snap", "PINS": "Pinterest",
    "ROKU": "Roku", "ABNB": "Airbnb", "LYFT": "Lyft",
    # USA - Fintech
    "V": "Visa", "MA": "Mastercard", "PYPL": "PayPal", "SQ": "Block",
    "AXP": "American Express", "FIS": "Fidelity National Info", "FISV": "Fiserv",
    # USA - Healthcare Pharma
    "LLY": "Eli Lilly", "ABBV": "AbbVie", "MRK": "Merck", "ABT": "Abbott",
    "AMGN": "Amgen", "GILD": "Gilead Sciences", "VRTX": "Vertex Pharmaceuticals",
    "REGN": "Regeneron", "BMY": "Bristol-Myers Squibb", "PFE": "Pfizer",
    "JNJ": "Johnson & Johnson", "MRNA": "Moderna", "BIIB": "Biogen",
    "ILMN": "Illumina", "ALNY": "Alnylam Pharmaceuticals", "RGEN": "Repligen",
    # USA - Healthcare Devices/Services
    "UNH": "UnitedHealth", "TMO": "Thermo Fisher Scientific", "DHR": "Danaher",
    "ISRG": "Intuitive Surgical", "MDT": "Medtronic", "BSX": "Boston Scientific",
    "BDX": "Becton Dickinson", "SYK": "Stryker", "ELV": "Elevance Health",
    "HUM": "Humana", "CI": "Cigna", "IDXX": "IDEXX Laboratories",
    "DXCM": "DexCom", "EW": "Edwards Lifesciences", "CVS": "CVS Health", "A": "Agilent",
    # USA - Financials
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "GS": "Goldman Sachs",
    "MS": "Morgan Stanley", "BLK": "BlackRock", "C": "Citigroup", "CB": "Chubb",
    "SCHW": "Charles Schwab", "SPGI": "S&P Global", "MCO": "Moody's",
    "CME": "CME Group", "ICE": "Intercontinental Exchange", "USB": "US Bancorp",
    "PGR": "Progressive", "PRU": "Prudential Financial", "MET": "MetLife",
    "AFL": "Aflac", "TRV": "Travelers", "PNC": "PNC Financial",
    "DFS": "Discover Financial", "COF": "Capital One", "MMC": "Marsh & McLennan",
    "BK": "BNY Mellon", "WFC": "Wells Fargo",
    # USA - Consumer Defensive
    "PG": "Procter & Gamble", "KO": "Coca-Cola", "PEP": "PepsiCo",
    "WMT": "Walmart", "COST": "Costco", "PM": "Philip Morris",
    "MCD": "McDonald's", "SBUX": "Starbucks", "KMB": "Kimberly-Clark",
    "CL": "Colgate-Palmolive", "MDLZ": "Mondelez", "GIS": "General Mills",
    "KR": "Kroger", "YUM": "Yum! Brands", "HSY": "Hershey", "STZ": "Constellation Brands",
    # USA - Consumer Cyclical
    "HD": "Home Depot", "LOW": "Lowe's", "TJX": "TJX Companies", "NKE": "Nike",
    "RACE": "Ferrari", "MAR": "Marriott", "HLT": "Hilton", "RCL": "Royal Caribbean",
    "EA": "Electronic Arts", "TTWO": "Take-Two Interactive", "LVS": "Las Vegas Sands",
    "MGM": "MGM Resorts",
    # USA - Energy
    "XOM": "ExxonMobil", "CVX": "Chevron", "EOG": "EOG Resources",
    "COP": "ConocoPhillips", "OXY": "Occidental Petroleum", "DVN": "Devon Energy",
    "HAL": "Halliburton", "SLB": "SLB", "VLO": "Valero Energy",
    "MPC": "Marathon Petroleum", "PSX": "Phillips 66", "WMB": "Williams Companies",
    "OKE": "ONEOK", "KMI": "Kinder Morgan",
    # USA - Industrials
    "CAT": "Caterpillar", "DE": "John Deere", "GE": "GE Aerospace",
    "ETN": "Eaton", "HON": "Honeywell", "ITW": "Illinois Tool Works",
    "EMR": "Emerson Electric", "WM": "Waste Management", "MMM": "3M",
    "RTX": "RTX", "NOC": "Northrop Grumman", "LMT": "Lockheed Martin",
    "LHX": "L3Harris Technologies", "FDX": "FedEx", "UPS": "UPS",
    "CSX": "CSX", "UNP": "Union Pacific", "GD": "General Dynamics",
    "ROK": "Rockwell Automation", "CMI": "Cummins", "CARR": "Carrier Global",
    "OTIS": "Otis Worldwide",
    # USA - Materials
    "SHW": "Sherwin-Williams", "DOW": "Dow", "DD": "DuPont",
    "LYB": "LyondellBasell", "ECL": "Ecolab", "FCX": "Freeport-McMoRan",
    "NEM": "Newmont", "PPG": "PPG Industries", "APD": "Air Products",
    # USA - Utilities
    "NEE": "NextEra Energy", "DUK": "Duke Energy", "SO": "Southern Company",
    "D": "Dominion Energy", "EXC": "Exelon", "AEP": "American Electric Power",
    "DTE": "DTE Energy", "SRE": "Sempra", "AWK": "American Water Works",
    # USA - Real Estate
    "PLD": "Prologis", "EQIX": "Equinix", "AMT": "American Tower",
    "CCI": "Crown Castle", "PSA": "Public Storage", "EQR": "Equity Residential",
    "AVB": "AvalonBay", "WELL": "Welltower",
    # Asia / global
    "TSM": "TSMC",
    # Europa - Germania (.DE)
    "ADS.DE": "adidas", "ALV.DE": "Allianz", "BAS.DE": "BASF",
    "BAYN.DE": "Bayer", "BEI.DE": "Beiersdorf", "BMW.DE": "BMW",
    "CON.DE": "Continental", "DBK.DE": "Deutsche Bank", "DB1.DE": "Deutsche Boerse",
    "EOAN.DE": "E.ON", "FRE.DE": "Fresenius", "HEN3.DE": "Henkel",
    "IFX.DE": "Infineon", "MRK.DE": "Merck KGaA", "MTX.DE": "MTU Aero Engines",
    "MUV2.DE": "Munich Re", "RWE.DE": "RWE", "SAP.DE": "SAP",
    "SIE.DE": "Siemens", "SHL.DE": "Siemens Healthineers", "VNA.DE": "Vonovia",
    "VOW3.DE": "Volkswagen", "DTE.DE": "Telekom Deutschland", "HNR1.DE": "Hannover Re",
    "MBG.DE": "Mercedes-Benz", "PAH3.DE": "Porsche Automobil", "1COV.DE": "Covestro",
    "ENR.DE": "Siemens Energy", "HFG.DE": "HelloFresh", "DHER.DE": "Delivery Hero",
    # Europa - Paesi Bassi (.AS)
    "AGN.AS": "Aegon", "ASM.AS": "ASM International", "ASML.AS": "ASML",
    "HEIA.AS": "Heineken", "IMCD.AS": "IMCD", "NN.AS": "NN Group",
    "PHIA.AS": "Philips", "RAND.AS": "Randstad", "AD.AS": "Ahold Delhaize",
    "WKL.AS": "Wolters Kluwer", "UNA.AS": "Unilever", "ADYEN.AS": "Adyen",
    # Europa - Francia (.PA)
    "AI.PA": "Air Liquide", "AIR.PA": "Airbus", "BNP.PA": "BNP Paribas",
    "GLE.PA": "Societe Generale", "KER.PA": "Kering", "MC.PA": "LVMH",
    "OR.PA": "L'Oreal", "PUB.PA": "Publicis", "RMS.PA": "Hermes",
    "SAN.PA": "Sanofi", "SU.PA": "Schneider Electric", "TTE.PA": "TotalEnergies",
    "CAP.PA": "Capgemini", "DSY.PA": "Dassault Systemes", "EL.PA": "EssilorLuxottica",
    "SGO.PA": "Saint-Gobain", "STM.PA": "STMicroelectronics",
    # Europa - Spagna (.MC)
    "ACS.MC": "ACS", "ANA.MC": "Acciona", "BBVA.MC": "BBVA",
    "IBE.MC": "Iberdrola", "ITX.MC": "Inditex (Zara)", "REP.MC": "Repsol",
    "SAN.MC": "Santander", "TEF.MC": "Telefonica", "FER.MC": "Ferrovial",
    # Europa - UK (.L)
    "BARC.L": "Barclays", "BP.L": "BP", "GLEN.L": "Glencore",
    "GSK.L": "GSK", "HSBA.L": "HSBC", "LLOY.L": "Lloyds Banking",
    "NWG.L": "NatWest", "RIO.L": "Rio Tinto", "SHEL.L": "Shell",
    "STAN.L": "Standard Chartered", "AZN.L": "AstraZeneca", "ULVR.L": "Unilever UK",
    "VOD.L": "Vodafone",
    # Europa - Italia (.MI)
    "ENI.MI": "Eni", "ENEL.MI": "Enel", "UCG.MI": "UniCredit",
    "ISP.MI": "Intesa Sanpaolo", "G.MI": "Generali", "LDO.MI": "Leonardo",
    "PRY.MI": "Prysmian", "MONC.MI": "Moncler", "CPR.MI": "Campari",
    "AMP.MI": "Amplifon", "BAMI.MI": "Banco BPM", "TIT.MI": "Telecom Italia",
    "SRG.MI": "Snam", "TRN.MI": "Terna", "STLAM.MI": "Stellantis",
    "MB.MI": "Mediobanca", "PIRC.MI": "Pirelli", "FBK.MI": "FinecoBank",
    "NEXI.MI": "Nexi",
}

# Indici globali — ticker Yahoo Finance : nome leggibile
WATCHLIST_INDICES = {
    "^GSPC":     "S&P 500",
    "^NDX":      "Nasdaq 100",
    "^DJI":      "Dow Jones",
    "^GDAXI":    "DAX",
    "^FTSE":     "FTSE 100",
    "^FCHI":     "CAC 40",
    "^STOXX50E": "Euro Stoxx 50",
}

LOOKBACK_PERIOD = "3y"
INTERVAL = "1wk"

# Numero di candidati Bloomberg V2 dopo pre-filtro
PRE_FILTER_TOP_N = 20

# Simulazione portfolio (yfinance, nessun broker)
PORTFOLIO_START  = 20_000.0   # EUR — capitale iniziale simulazione
TRADE_SIZE_EUR   = 500.0      # EUR per trade (~2.5% del capitale)
MAX_OPEN_TRADES  = 3
