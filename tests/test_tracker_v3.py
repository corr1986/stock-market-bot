import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tracker_v3 import update_chandelier_stop, should_close


def _make_pos(max_high, atr, initial_sl, chandelier_stop):
    return {
        "ticker": "TEST", "status": "active",
        "entry_price": 100.0, "atr_entry": atr,
        "initial_sl": initial_sl,
        "max_high_since_entry": max_high,
        "chandelier_stop": chandelier_stop,
    }


def test_chandelier_updated_on_new_high():
    pos = _make_pos(max_high=105.0, atr=2.5, initial_sl=95.0, chandelier_stop=100.0)
    updated = update_chandelier_stop(pos, 110.0)
    assert updated["max_high_since_entry"] == 110.0
    assert updated["chandelier_stop"] == 105.0  # 110 - 2*2.5


def test_chandelier_not_lowered_on_lower_high():
    pos = _make_pos(max_high=110.0, atr=2.5, initial_sl=95.0, chandelier_stop=105.0)
    updated = update_chandelier_stop(pos, 108.0)
    assert updated["max_high_since_entry"] == 110.0
    assert updated["chandelier_stop"] == 105.0


def test_should_close_when_low_hits_stop():
    pos = _make_pos(max_high=110.0, atr=2.5, initial_sl=95.0, chandelier_stop=105.0)
    assert should_close(104.5, pos) is True


def test_should_not_close_when_above_stop():
    pos = _make_pos(max_high=110.0, atr=2.5, initial_sl=95.0, chandelier_stop=105.0)
    assert should_close(106.0, pos) is False


def test_initial_sl_as_floor_when_chandelier_below():
    # chandelier=94 < initial_sl=95 → active_stop=max(94,95)=95
    pos = _make_pos(max_high=99.0, atr=2.5, initial_sl=95.0, chandelier_stop=94.0)
    assert should_close(94.5, pos) is True   # 94.5 <= 95 → chiude (initial_sl è il floor)
    assert should_close(95.0, pos) is True   # 95.0 <= 95 → chiude
    assert should_close(95.5, pos) is False  # 95.5 > 95 → non chiude
