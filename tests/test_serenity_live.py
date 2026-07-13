import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date

from serenity_live import (
    plan_entry, activate, check_exit, close_position, mark_price,
    invested_capital, HOLD_DAYS, SIZE_EUR, SL_ATR_MULT,
)


def test_activate_sets_entry_deadline_sl():
    pos = plan_entry("NBIS", entry_ref=100.0, atr=2.5, signal_date=date(2026, 3, 1))
    activate(pos, entry_price=102.0, entry_day=date(2026, 3, 2))
    assert pos["status"] == "active"
    assert pos["entry_price"] == 102.0
    assert pos["entry_date"] == "2026-03-02"
    assert abs(pos["initial_sl"] - 97.0) < 1e-9   # 102 - 2*2.5
    assert pos["deadline"] == "2026-05-01"          # +60 giorni


def test_close_position_pnl():
    pos = {"shares": 5, "entry_price": 100.0, "status": "active"}
    close_position(pos, exit_price=112.0, exit_day=date(2026, 4, 1), reason="deadline")
    assert pos["status"] == "closed"
    assert pos["close_reason"] == "deadline"
    assert abs(pos["pnl_eur"] - 60.0) < 1e-9        # 5 * 12
    assert abs(pos["pnl_pct"] - 12.0) < 1e-9


def test_mark_price_unrealized():
    pos = {"shares": 5, "entry_price": 100.0}
    mark_price(pos, 108.0)
    assert pos["current_price"] == 108.0
    assert abs(pos["unrealized_eur"] - 40.0) < 1e-9
    assert abs(pos["unrealized_pct"] - 8.0) < 1e-9


def test_invested_capital():
    pf = {"open": [{"size_eur": 500.0}, {"size_eur": 800.0}]}
    assert abs(invested_capital(pf) - 1300.0) < 1e-9
    assert invested_capital({}) == 0


# ---------- plan_entry: crea una posizione pending da un segnale ----------

def test_plan_entry_whole_shares_and_sl():
    # entry_ref 100, atr 2.5 -> SL = 100 - 2*2.5 = 95; shares = floor(500/100)=5
    pos = plan_entry("NBIS", entry_ref=100.0, atr=2.5, signal_date=date(2026, 3, 1))
    assert pos["ticker"] == "NBIS"
    assert pos["status"] == "pending"
    assert pos["shares"] == 5
    assert abs(pos["initial_sl"] - 95.0) < 1e-9
    assert abs(pos["size_eur"] - 500.0) < 1e-9  # 5 * 100
    assert pos["signal_date"] == "2026-03-01"
    assert pos["deadline"] is None  # fissato all'attivazione


def test_plan_entry_minimum_one_share():
    # prezzo 800 > size 500 -> comunque 1 azione
    pos = plan_entry("ASML", entry_ref=800.0, atr=20.0, signal_date=date(2026, 3, 1))
    assert pos["shares"] == 1
    assert abs(pos["size_eur"] - 800.0) < 1e-9


def test_plan_entry_rejects_bad_atr():
    assert plan_entry("X", entry_ref=100.0, atr=0.0, signal_date=date(2026, 3, 1)) is None
    assert plan_entry("X", entry_ref=0.0, atr=2.0, signal_date=date(2026, 3, 1)) is None


# ---------- check_exit: regole hold-60 ----------

def _active(entry=100.0, sl=95.0, entry_date="2026-03-02", shares=5):
    return {
        "ticker": "NBIS", "status": "active", "shares": shares,
        "entry_price": entry, "initial_sl": sl,
        "entry_date": entry_date, "deadline": "2026-05-01",  # +60gg
    }


def test_exit_stop_loss_intraday():
    # low tocca lo SL -> exit allo SL
    pos = _active()
    res = check_exit(pos, low=94.0, close=96.0, open_=97.0,
                     today=date(2026, 3, 10), bearish=False)
    assert res is not None
    assert res["reason"] == "stop_loss"
    assert abs(res["exit_price"] - 95.0) < 1e-9


def test_exit_stop_loss_gap_down_uses_open():
    # open sotto lo SL -> exit realistico all'open, non allo SL
    pos = _active()
    res = check_exit(pos, low=88.0, close=89.0, open_=90.0,
                     today=date(2026, 3, 10), bearish=False)
    assert res["reason"] == "stop_loss"
    assert abs(res["exit_price"] - 90.0) < 1e-9


def test_exit_deadline_at_close():
    # oggi >= deadline -> exit al close
    pos = _active()
    res = check_exit(pos, low=101.0, close=110.0, open_=105.0,
                     today=date(2026, 5, 1), bearish=False)
    assert res["reason"] == "deadline"
    assert abs(res["exit_price"] - 110.0) < 1e-9


def test_exit_bearish_stance_at_close():
    pos = _active()
    res = check_exit(pos, low=101.0, close=112.0, open_=108.0,
                     today=date(2026, 3, 20), bearish=True)
    assert res["reason"] == "bearish"
    assert abs(res["exit_price"] - 112.0) < 1e-9


def test_exit_stop_priority_over_deadline():
    # se sia SL sia deadline scattano lo stesso giorno, vince lo SL (conservativo)
    pos = _active()
    res = check_exit(pos, low=90.0, close=110.0, open_=96.0,
                     today=date(2026, 5, 1), bearish=True)
    assert res["reason"] == "stop_loss"


def test_no_exit_when_holding():
    pos = _active()
    assert check_exit(pos, low=101.0, close=105.0, open_=103.0,
                      today=date(2026, 3, 15), bearish=False) is None


def test_constants():
    assert HOLD_DAYS == 60
    assert SIZE_EUR == 500.0
    assert SL_ATR_MULT == 2.0
