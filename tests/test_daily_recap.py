"""Test per daily_recap: resoconto giornaliero dei 4 portafogli via Telegram."""

from daily_recap import summarize_standard, summarize_insider, build_message


# ── summarize_standard (V1 / V3 / Serenity) ────────────────────────────────

def test_summarize_standard_basic():
    d = {
        "balance": 19790.98,
        "realized_pnl": -209.02,
        "unrealized_pnl": 283.56,
        "open": [{"t": 1}, {"t": 2}, {"t": 3}],
        "closed": [{"t": 1}, {"t": 2}],
    }
    s = summarize_standard(d)
    assert s["saldo"] == 19790.98
    assert s["equity"] == 20074.54
    assert s["aperti"] == 3
    assert s["chiusi"] == 2
    assert s["pnl_aperti"] == 283.56      # non realizzato delle aperte
    assert s["pnl_chiusi"] == -209.02     # realizzato delle chiuse


def test_summarize_standard_handles_missing_unrealized():
    d = {"balance": 20000.0, "open": [], "closed": []}
    s = summarize_standard(d)
    assert s["equity"] == 20000.0
    assert s["aperti"] == 0 and s["chiusi"] == 0


# ── summarize_insider ──────────────────────────────────────────────────────

def test_summarize_insider_equity_includes_invested_and_unrealized():
    d = {
        "cash": 18637.95,
        "positions": [
            {"invested": 1000.0, "unrealized_pnl": 5.0},
            {"invested": 500.0, "unrealized_pnl": None},  # pending, non prezzata
        ],
        "closed": [{"pnl": 16.32}, {"pnl": -821.46}, {"pnl": 100.0}],
    }
    s = summarize_insider(d)
    assert s["saldo"] == 18637.95
    assert s["equity"] == 18637.95 + 1000.0 + 5.0 + 500.0
    assert s["aperti"] == 2
    assert s["chiusi"] == 3
    assert s["pnl_aperti"] == 5.0
    assert s["pnl_chiusi"] == round(16.32 - 821.46 + 100.0, 2)


# ── build_message ──────────────────────────────────────────────────────────

def test_build_message_contains_all_portfolios_and_counts():
    s = {"saldo": 20000.0, "equity": 20150.75, "aperti": 12, "chiusi": 3,
         "pnl_aperti": 283.56, "pnl_chiusi": -209.02}
    msg = build_message(v1=s, v3=s, insider=s, serenity=s)
    for name in ("V1", "V3", "Insider", "Serenity"):
        assert name in msg
    assert "20.000" in msg      # saldo formattato
    assert "20.151" in msg      # equity arrotondata
    assert "12" in msg and "3" in msg
    assert "+284" in msg        # P&L aperte col segno
    assert "-209" in msg        # P&L chiuse col segno


def test_build_message_insider_in_usd():
    eur = {"saldo": 20000.0, "equity": 20000.0, "aperti": 0, "chiusi": 0,
           "pnl_aperti": 0.0, "pnl_chiusi": 0.0}
    usd = {"saldo": 18637.95, "equity": 19640.0, "aperti": 1, "chiusi": 3,
           "pnl_aperti": 5.0, "pnl_chiusi": -705.14}
    msg = build_message(v1=eur, v3=eur, insider=usd, serenity=eur)
    assert "$" in msg           # insider in dollari
    assert "€" in msg           # gli altri in euro
