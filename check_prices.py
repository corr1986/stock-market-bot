import yfinance as yf
from datetime import datetime

tickers = ['BP.L', 'ALV.DE', 'PM']
entries = {'BP.L': 547.2, 'ALV.DE': 378.0, 'PM': 191.0}

print(f"Orario check: {datetime.now().strftime('%H:%M:%S')}")
print()

for t in tickers:
    # Prezzo via H1 (come usa tracker.py)
    df = yf.download(t, period='7d', interval='1h', progress=False, auto_adjust=True)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    last_close_h1 = round(float(df['Close'].iloc[-1]), 2)
    last_bar_time = df.index[-1]

    # Prezzo real-time via fast_info
    fi = yf.Ticker(t).fast_info
    rt_price = round(fi.last_price, 2)

    entry = entries[t]
    pnl_h1 = (last_close_h1 - entry) / entry * 100
    pnl_rt  = (rt_price - entry) / entry * 100

    print(f"{t}:")
    print(f"  H1 last close : {last_close_h1}  (barra: {last_bar_time})  P&L {pnl_h1:+.2f}%")
    print(f"  Real-time     : {rt_price}  P&L {pnl_rt:+.2f}%")
    print()
