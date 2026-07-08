import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date

import pandas as pd

from backtest_serenity import compute_atr, simulate_trade, run_backtest


def _flat_df(start="2026-01-02", days=60, price=100.0):
    idx = pd.bdate_range(start, periods=days)
    return pd.DataFrame(
        {"Open": price, "High": price + 1, "Low": price - 1, "Close": price},
        index=idx,
    )


def _sig(ticker, d):
    return {"ticker": ticker, "date": d,
            "stance": {"stance": "bullish", "conviction": 5}}


def test_run_backtest_respects_max_positions():
    # 4 segnali lo stesso giorno, prezzi piatti (nessuna exit) -> solo 3 trade
    prices = {t: _flat_df() for t in ["AAA", "BBB", "CCC", "DDD"]}
    vix = pd.Series(15.0, index=_flat_df().index)
    signals = [_sig(t, date(2026, 2, 2)) for t in ["AAA", "BBB", "CCC", "DDD"]]
    trades = run_backtest(signals, prices, vix)
    assert len(trades) == 3


def test_run_backtest_vix_blocks_entry():
    prices = {"AAA": _flat_df()}
    idx = _flat_df().index
    vix = pd.Series(35.0, index=idx)  # risk-off
    trades = run_backtest([_sig("AAA", date(2026, 2, 2))], prices, vix)
    assert trades == []


def test_run_backtest_skips_low_conviction_and_non_bullish():
    prices = {"AAA": _flat_df(), "BBB": _flat_df()}
    vix = pd.Series(15.0, index=_flat_df().index)
    signals = [
        {"ticker": "AAA", "date": date(2026, 2, 2),
         "stance": {"stance": "bullish", "conviction": 3}},
        {"ticker": "BBB", "date": date(2026, 2, 2),
         "stance": {"stance": "bearish", "conviction": 5}},
    ]
    assert run_backtest(signals, prices, vix) == []


def test_run_backtest_missing_prices_skipped():
    vix = pd.Series(15.0, index=_flat_df().index)
    assert run_backtest([_sig("ZZZ", date(2026, 2, 2))], {}, vix) == []


def test_run_backtest_frees_slot_after_exit():
    # AAA esce subito (crollo), un quarto segnale piu' tardi trova posto
    crash = _flat_df().copy()
    crash_day = crash.index[25]
    crash.loc[crash_day, ["Open", "High", "Low", "Close"]] = [80, 82, 78, 80]
    prices = {"AAA": crash, "BBB": _flat_df(), "CCC": _flat_df(), "DDD": _flat_df()}
    vix = pd.Series(15.0, index=_flat_df().index)
    signals = [_sig(t, date(2026, 2, 2)) for t in ["AAA", "BBB", "CCC"]]
    signals.append(_sig("DDD", date(2026, 3, 20)))  # dopo l'exit di AAA
    trades = run_backtest(signals, prices, vix)
    assert len(trades) == 4


def _df(rows):
    """rows: list of (date_str, open, high, low, close)"""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame(
        {"Open": [r[1] for r in rows], "High": [r[2] for r in rows],
         "Low": [r[3] for r in rows], "Close": [r[4] for r in rows]},
        index=idx,
    )


def test_compute_atr_constant_range():
    # 20 giorni con range costante 2.0 e nessun gap -> ATR(14) = 2.0
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(1, 21)]
    atr = compute_atr(_df(rows), period=14)
    assert abs(atr.iloc[-1] - 2.0) < 1e-9


def test_simulate_trade_stop_hit():
    # entry al primo giorno dopo l'evento: open=100, ATR costante 2 -> SL iniziale = 96
    # il prezzo scende sotto 96 il 2026-02-05 -> exit a 96
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(2, 31)]
    rows += [
        # High=100: il chandelier non sale sopra lo stop iniziale 96
        ("2026-02-02", 100, 100, 99, 100),   # entry day (open 100)
        ("2026-02-03", 100, 100, 99, 100),
        ("2026-02-04", 100, 100, 99, 100),
        ("2026-02-05", 97, 97, 90, 91),      # low 90 < stop 96 -> exit
    ]
    trade = simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0)
    assert trade is not None
    assert trade["entry_date"] == date(2026, 2, 2)
    assert abs(trade["entry"] - 100.0) < 1e-9
    assert trade["exit_date"] == date(2026, 2, 5)
    assert abs(trade["exit"] - 96.0) < 1e-9   # stop = 100 - 2*2
    # size = risk / sl_pct = 40 / 0.04 = 1000 EUR; pnl = -4% * 1000 = -40 EUR
    assert abs(trade["size_eur"] - 1000.0) < 1e-6
    assert abs(trade["pnl_eur"] - (-40.0)) < 1e-6


def test_simulate_trade_chandelier_trails_up():
    # il prezzo sale: il chandelier segue il max high e l'exit avviene in profitto
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(2, 31)]
    rows += [
        ("2026-02-02", 100, 101, 99, 100),    # entry open 100, stop 96
        ("2026-02-03", 104, 110, 103, 109),   # max_high 110 -> stop 106
        ("2026-02-04", 108, 109, 105, 106),   # low 105 < stop 106 -> exit 106
    ]
    trade = simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0)
    assert abs(trade["exit"] - 106.0) < 1e-9
    assert trade["pnl_eur"] > 0


def test_simulate_trade_gap_down_exits_at_open():
    # gap sotto lo stop: exit realistico all'open, non allo stop
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(2, 31)]
    rows += [
        ("2026-02-02", 100, 101, 99, 100),   # entry, stop 96
        ("2026-02-03", 90, 92, 88, 91),      # open 90 < stop 96 -> exit a 90
    ]
    trade = simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0)
    assert abs(trade["exit"] - 90.0) < 1e-9


def test_simulate_trade_still_open_closes_at_last_close():
    rows = [(f"2026-01-{d:02d}", 100, 101, 99, 100) for d in range(2, 31)]
    rows += [
        ("2026-02-02", 100, 101, 99, 100),
        ("2026-02-03", 100, 101, 99.5, 100.5),
    ]
    trade = simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0)
    assert trade["exit_date"] == date(2026, 2, 3)
    assert trade["open_at_end"] is True


def test_simulate_trade_insufficient_history_returns_none():
    rows = [("2026-02-02", 100, 101, 99, 100)]  # niente storico per ATR
    assert simulate_trade(_df(rows), event_date=date(2026, 2, 1), risk_eur=40.0) is None
