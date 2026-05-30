"""
analyze_universe.py — Analisi statistica universo 247 ticker (backtest ottimale)
"""
import pickle
import pandas as pd
import numpy as np
from config import WATCHLIST_USA, WATCHLIST_EUROPE

with open('market_data.pkl', 'rb') as f:
    data = pickle.load(f)

# ---------------------------------------------------------------------------
# Mappa settori
# ---------------------------------------------------------------------------
sector_map = {
    'AAPL':'Tech','MSFT':'Tech','NVDA':'Tech','GOOGL':'Tech','GOOG':'Tech',
    'META':'Tech','AMZN':'Tech','TSLA':'Tech','AVGO':'Tech','TSM':'Tech',
    'AMD':'Semis','QCOM':'Semis','TXN':'Semis','ADI':'Semis','MU':'Semis',
    'AMAT':'Semis','KLAC':'Semis','SNPS':'Semis','NXPI':'Semis','MRVL':'Semis',
    'INTC':'Semis','CDNS':'Semis',
    'CRM':'Software','ADBE':'Software','NOW':'Software','PANW':'Software',
    'INTU':'Software','ORCL':'Software','IBM':'Software','CSCO':'Software',
    'FTNT':'Software','DDOG':'Software','ZM':'Software','WDAY':'Software',
    'OKTA':'Software','DOCU':'Software','SNOW':'Software','TWLO':'Software',
    'NFLX':'Media/Internet','DIS':'Media/Internet','SPOT':'Media/Internet',
    'SHOP':'Media/Internet','MELI':'Media/Internet','BKNG':'Media/Internet',
    'EBAY':'Media/Internet','UBER':'Media/Internet','TTD':'Media/Internet',
    'SNAP':'Media/Internet','PINS':'Media/Internet','ROKU':'Media/Internet',
    'HD':'Consumer Cycl.','LOW':'Consumer Cycl.','TJX':'Consumer Cycl.',
    'NKE':'Consumer Cycl.','RACE':'Consumer Cycl.','MAR':'Consumer Cycl.',
    'HLT':'Consumer Cycl.','EA':'Consumer Cycl.','TTWO':'Consumer Cycl.',
    'V':'Finance','MA':'Finance','PYPL':'Finance','AXP':'Finance',
    'JPM':'Finance','BAC':'Finance','GS':'Finance','MS':'Finance',
    'BLK':'Finance','C':'Finance','CB':'Finance','SCHW':'Finance',
    'SPGI':'Finance','MCO':'Finance','CME':'Finance','ICE':'Finance',
    'PGR':'Finance','USB':'Finance','PRU':'Finance','MET':'Finance',
    'AFL':'Finance','TRV':'Finance','PNC':'Finance','COF':'Finance','BK':'Finance',
    'LLY':'Healthcare','ABBV':'Healthcare','MRK':'Healthcare','ABT':'Healthcare',
    'AMGN':'Healthcare','GILD':'Healthcare','VRTX':'Healthcare','REGN':'Healthcare',
    'PFE':'Healthcare','JNJ':'Healthcare','MRNA':'Healthcare','BIIB':'Healthcare',
    'BMY':'Healthcare','ILMN':'Healthcare','UNH':'Healthcare','TMO':'Healthcare',
    'DHR':'Healthcare','ISRG':'Healthcare','MDT':'Healthcare','BSX':'Healthcare',
    'BDX':'Healthcare','SYK':'Healthcare','ELV':'Healthcare','DXCM':'Healthcare',
    'HUM':'Healthcare','CI':'Healthcare','A':'Healthcare','IDXX':'Healthcare',
    'EW':'Healthcare','CVS':'Healthcare',
    'PG':'Staples','KO':'Staples','PEP':'Staples','WMT':'Staples','COST':'Staples',
    'PM':'Staples','MCD':'Staples','SBUX':'Staples','KMB':'Staples','CL':'Staples',
    'MDLZ':'Staples','GIS':'Staples','KR':'Staples','YUM':'Staples','HSY':'Staples',
    'XOM':'Energy','CVX':'Energy','EOG':'Energy','COP':'Energy','OXY':'Energy',
    'DVN':'Energy','HAL':'Energy','SLB':'Energy','PSX':'Energy','VLO':'Energy',
    'MPC':'Energy','WMB':'Energy','OKE':'Energy','KMI':'Energy',
    'CAT':'Industrials','DE':'Industrials','GE':'Industrials','ETN':'Industrials',
    'HON':'Industrials','ITW':'Industrials','EMR':'Industrials','WM':'Industrials',
    'MMM':'Industrials','RTX':'Industrials','NOC':'Industrials','LMT':'Industrials',
    'LHX':'Industrials','FDX':'Industrials','UPS':'Industrials','CSX':'Industrials',
    'UNP':'Industrials','GD':'Industrials','ROK':'Industrials','CMI':'Industrials',
    'SHW':'Materials','DOW':'Materials','DD':'Materials','LYB':'Materials',
    'ECL':'Materials','FCX':'Materials','NEM':'Materials','PPG':'Materials',
    'NEE':'Utilities','DUK':'Utilities','SO':'Utilities','D':'Utilities',
    'EXC':'Utilities','AEP':'Utilities','DTE':'Utilities','SRE':'Utilities',
    'PLD':'Real Estate','EQIX':'Real Estate','AMT':'Real Estate','CCI':'Real Estate',
    'PSA':'Real Estate','EQR':'Real Estate','AVB':'Real Estate',
}
for t in WATCHLIST_EUROPE:
    if '.DE' in t:   sector_map[t] = 'EU-Germania'
    elif '.AS' in t: sector_map[t] = 'EU-Olanda'
    elif '.PA' in t: sector_map[t] = 'EU-Francia'
    elif '.MC' in t: sector_map[t] = 'EU-Spagna'
    elif '.L' in t:  sector_map[t] = 'EU-UK'

# ---------------------------------------------------------------------------
# Stats per ogni ticker
# ---------------------------------------------------------------------------
rows = []
for ticker, df in data.items():
    df2 = df[(df.index >= '2020-01-01') & (df.index <= '2026-04-30')].copy()
    if len(df2) < 20:
        continue
    first = float(df2['Close'].iloc[0])
    last  = float(df2['Close'].iloc[-1])
    if first <= 0:
        continue
    years = (df2.index[-1] - df2.index[0]).days / 365.25
    ann_ret = ((last / first) ** (1 / years) - 1) * 100 if years > 0 else 0
    weekly_ret = df2['Close'].pct_change().dropna()
    vol = weekly_ret.std() * np.sqrt(52) * 100
    sharpe = ann_ret / vol if vol > 0 else 0
    dd = ((df2['Close'] - df2['Close'].cummax()) / df2['Close'].cummax() * 100).min()

    # Anno per anno
    yr_rets = {}
    for yr in range(2020, 2027):
        sub = df2[df2.index.year == yr]['Close']
        if len(sub) >= 2:
            yr_rets[yr] = round((float(sub.iloc[-1]) / float(sub.iloc[0]) - 1) * 100, 1)

    rows.append({
        'ticker': ticker,
        'sector': sector_map.get(ticker, 'Other'),
        'geo': 'EU' if any(ticker.endswith(s) for s in ['.DE','.AS','.PA','.MC','.L','.MI']) else 'USA',
        'ann_ret': round(ann_ret, 1),
        'vol': round(vol, 1),
        'sharpe': round(sharpe, 2),
        'max_dd': round(dd, 1),
        'yr_rets': yr_rets,
    })

df_stats = pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# Backtest strategy stats (from existing computation)
# ---------------------------------------------------------------------------
trades = pd.read_csv('backtest_eu_combined_trades.csv')
closed = trades[trades['outcome'].isin(['WIN', 'LOSS', 'TIMEOUT'])].copy()

TRADE_SIZE = 500
CAPITAL = 20_000

wins    = closed[closed['outcome'] == 'WIN']
losses  = closed[closed['outcome'] == 'LOSS']
timeouts = closed[closed['outcome'] == 'TIMEOUT']

wr      = len(wins) / len(closed) * 100
avg_win = wins['pnl_pct'].mean()
avg_los = losses['pnl_pct'].mean()
ev_pct  = (wr/100)*avg_win + (1-wr/100)*avg_los
ev_eur  = ev_pct / 100 * TRADE_SIZE

total_pnl   = (closed['pnl_pct'] / 100 * TRADE_SIZE).sum()
net_profit  = total_pnl - max(0, total_pnl * 0.26)
ann_net     = net_profit / 6.33
ann_pct     = ann_net / CAPITAL * 100

# Equity curve per max drawdown
balance = CAPITAL
balances = []
for _, row in closed.sort_values('date').iterrows():
    balance += row['pnl_pct'] / 100 * TRADE_SIZE
    balances.append(balance)
bal_arr = np.array(balances)
max_bal = np.maximum.accumulate(bal_arr)
dd_arr  = (bal_arr - max_bal) / max_bal * 100
strat_max_dd = dd_arr.min()

# Consecutive losses
max_cl = curr = 0
for _, row in closed.sort_values('date').iterrows():
    if row['outcome'] == 'LOSS':
        curr += 1
        max_cl = max(max_cl, curr)
    else:
        curr = 0

# Per anno
yearly = {}
for _, row in closed.sort_values('date').iterrows():
    yr = int(row['year'])
    yearly[yr] = yearly.get(yr, 0) + row['pnl_pct'] / 100 * TRADE_SIZE

# Ticker più frequenti come segnali
top_tickers = closed['ticker'].value_counts().head(15)

# Monte Carlo projection 12 mesi (52 settimane, top 3 → ~3 trade/sett)
np.random.seed(42)
pnl_dist = closed['pnl_pct'].values
n_sim    = 10_000
weeks    = 52
trades_per_year = len(closed) / 6.33

sim_results = []
for _ in range(n_sim):
    n_trades = int(np.random.poisson(trades_per_year))
    sampled  = np.random.choice(pnl_dist, size=n_trades, replace=True)
    gross    = (sampled / 100 * TRADE_SIZE).sum()
    net      = gross - max(0, gross * 0.26)
    sim_results.append(net)

sim_arr = np.array(sim_results)
mc_p10  = np.percentile(sim_arr, 10)
mc_p25  = np.percentile(sim_arr, 25)
mc_med  = np.percentile(sim_arr, 50)
mc_p75  = np.percentile(sim_arr, 75)
mc_p90  = np.percentile(sim_arr, 90)
mc_prob_pos = (sim_arr > 0).mean() * 100

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
print("=== UNIVERSE STATS ===")
print(f"Ticker: {len(df_stats)}")
print(f"Ann ret medio: {df_stats['ann_ret'].mean():.1f}%")
print(f"Mediana:       {df_stats['ann_ret'].median():.1f}%")
print(f"Std:           {df_stats['ann_ret'].std():.1f}%")
print(f"Vol media:     {df_stats['vol'].mean():.1f}%")
print(f"Sharpe medio:  {df_stats['sharpe'].mean():.2f}")
print(f"MaxDD medio:   {df_stats['max_dd'].mean():.1f}%")

print("\n=== PER SETTORE ===")
sect_g = df_stats.groupby('sector').agg(
    n=('ticker','count'),
    ann_med=('ann_ret','median'),
    ann_avg=('ann_ret','mean'),
    vol=('vol','mean'),
    sharpe=('sharpe','mean'),
).sort_values('ann_med', ascending=False).round(1)
print(sect_g.to_string())

print("\n=== DISTRIBUZIONE ANN RET ===")
for lo, hi in [(-999,-20),(-20,-10),(-10,0),(0,10),(10,20),(20,35),(35,999)]:
    n = len(df_stats[(df_stats['ann_ret']>=lo)&(df_stats['ann_ret']<hi)])
    label = f"{lo:+4d}% a {'+inf' if hi==999 else f'{hi:+4d}%'}"
    print(f"  {label}: {n:3d} ticker ({n/len(df_stats)*100:.0f}%)")

print("\n=== STRATEGY BACKTEST (SL=2.0 RR=2.0, Top3) ===")
print(f"Trade chiusi: {len(closed)} | WIN: {len(wins)} | LOSS: {len(losses)} | TIMEOUT: {len(timeouts)}")
print(f"Win Rate: {wr:.1f}%")
print(f"Avg WIN:  {avg_win:+.2f}%  Avg LOSS: {avg_los:+.2f}%")
print(f"EV/trade: {ev_eur:+.2f} EUR  ({ev_pct:+.3f}%)")
print(f"Profitto netto totale 6.33 anni: {net_profit:+.0f} EUR")
print(f"Annuo netto: {ann_net:+.0f} EUR  ({ann_pct:+.1f}%)")
print(f"Max Drawdown strategia: {strat_max_dd:.1f}%")
print(f"Max SL consecutivi:     {max_cl}")

print("\n=== PER ANNO ===")
for yr in sorted(yearly.keys()):
    g = yearly[yr]
    t = max(0, g*0.26)
    print(f"  {yr}: lordo {g:+.0f}E  tasse -{t:.0f}E  netto {g-t:+.0f}E")

print("\n=== TOP 15 TICKER PIU SEGNALATI ===")
for tk, cnt in top_tickers.items():
    w = closed[(closed['ticker']==tk)&(closed['outcome']=='WIN')]
    l = closed[(closed['ticker']==tk)&(closed['outcome']=='LOSS')]
    wr_tk = len(w)/(len(w)+len(l))*100 if (len(w)+len(l))>0 else 0
    print(f"  {tk:12s} {cnt:3d}x  WR={wr_tk:.0f}%")

print("\n=== MONTE CARLO 12 MESI (10.000 simulazioni) ===")
print(f"  Prob profitto positivo: {mc_prob_pos:.1f}%")
print(f"  P10 (scenario pessimista):  {mc_p10:+.0f} EUR netto")
print(f"  P25:                        {mc_p25:+.0f} EUR netto")
print(f"  P50 (scenario atteso):      {mc_med:+.0f} EUR netto")
print(f"  P75:                        {mc_p75:+.0f} EUR netto")
print(f"  P90 (scenario ottimista):   {mc_p90:+.0f} EUR netto")

print("\n=== TOP 15 PERFORMER UNIVERSO ===")
for _, r in df_stats.nlargest(15, 'ann_ret').iterrows():
    print(f"  {r['ticker']:12s} {r['ann_ret']:+6.1f}%/ann  Sharpe={r['sharpe']:5.2f}  MaxDD={r['max_dd']:6.1f}%")

print("\n=== BOTTOM 10 PERFORMER UNIVERSO ===")
for _, r in df_stats.nsmallest(10, 'ann_ret').iterrows():
    print(f"  {r['ticker']:12s} {r['ann_ret']:+6.1f}%/ann  Sharpe={r['sharpe']:5.2f}  MaxDD={r['max_dd']:6.1f}%")

print("\n=== GEO: USA vs EU ===")
print(df_stats.groupby('geo')[['ann_ret','vol','sharpe','max_dd']].mean().round(2))
