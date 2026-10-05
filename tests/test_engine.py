from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from quantrail.core import Instrument
from quantrail.engine import run_target_weights


class ZeroCosts:
    commission_rate = 0

    def fees(self, instrument, side, quantity, price, day):
        return Decimal(0), Decimal(0)


class FlatFee:
    """20 per order, 0.1% tax on sells: enough to exercise cost paths."""
    commission_rate = 0

    def fees(self, instrument, side, quantity, price, day):
        value = Decimal(quantity) * Decimal(price)
        return Decimal(20), (value * Decimal("0.001")).quantize(Decimal(1)) if side == "SELL" else Decimal(0)


ETF = Instrument("X:ETF", "X", "etf", "TWD")


def market(opens, closes, *, suspended=(), actions=()):
    days = pd.bdate_range("2024-01-01", periods=len(opens) + 5)
    rows, cal = [], []
    for i, day in enumerate(days[:len(opens)]):
        if i in suspended:
            cal.append({"session_date": day, "asset_tradable": False, "reason": "SUSPENDED"})
            continue
        rows.append({"session_date": day, "open": opens[i], "close": closes[i], "quote_valid": True})
        cal.append({"session_date": day, "asset_tradable": True, "reason": ""})
    columns = ["action_id", "action_type", "effective_date", "ex_date", "payment_date",
               "split_new_per_old", "cash_per_entitled_unit"]
    acts = pd.DataFrame(list(actions), columns=columns)
    sessions = list(days.date)

    def settle(d):
        return [s for s in sessions if s > d][1]

    return dict(prices=pd.DataFrame(rows), calendar=pd.DataFrame(cal), actions=acts, settle=settle), days


ZERO = ZeroCosts()


def run(m, days, instrument=ETF, costs=ZERO, **kw):
    return run_target_weights(instrument=instrument, costs=costs, **m, start=days[0],
                              end=days[len(m["calendar"]) - 1], capital=10_000, **kw)


def test_split_leaves_wealth_unchanged():
    days = pd.bdate_range("2024-01-01", periods=6)
    split = ("S", "SPLIT", days[3], pd.NaT, pd.NaT, 4.0, np.nan)
    m, days = market([100] * 3 + [25] * 3, [100] * 3 + [25] * 3, actions=[split])
    r = run(m, days, initial_target=1.0)
    assert r.daily["units"].tolist() == [100, 100, 100, 400, 400, 400]
    assert np.allclose(r.daily["nav"], 10_000) and np.allclose(r.daily["identity_residual"], 0)


def test_close_decision_fills_at_the_next_open():
    m, days = market([100, 100, 110, 120], [100, 105, 115, 120])
    r = run(m, days, initial_target=1.0, decisions=pd.Series({days[1]: 0.0}))
    assert r.daily["units"].tolist() == [100, 100, 0, 0]
    assert r.orders.iloc[-1]["fill_price"] == 110


def test_suspended_session_defers_the_fill():
    m, days = market([100] * 4, [100] * 4, suspended={2})
    r = run(m, days, initial_target=1.0, decisions=pd.Series({days[1]: 0.0}))
    assert "SUSPENDED" in r.events.loc[r.events["type"] == "NO_FILL", "detail"].tolist()
    assert r.orders.iloc[-1]["date"] == days[3]


def test_dividend_is_reinvested_buy_only_and_capped_after_payment():
    days = pd.bdate_range("2024-01-01", periods=8)
    div = ("D", "CASH_DISTRIBUTION", days[2], days[2], days[4], np.nan, 10.0)
    m, days = market([100, 100, 90, 50, 50, 50, 50, 50], [100, 100, 90, 50, 50, 50, 50, 50], actions=[div])
    r = run(m, days, initial_target=0.5)
    assert r.daily.loc[days[2], "receivable"] == 500
    reinvest = r.orders[r.orders["reinvestment"]]
    assert reinvest["date"].tolist() == [days[5]] and reinvest["quantity"].tolist() == [10]


def test_cash_target_does_not_rebuy_with_dividends():
    days = pd.bdate_range("2024-01-01", periods=8)
    div = ("D", "CASH_DISTRIBUTION", days[1], days[1], days[4], np.nan, 5.0)
    m, days = market([100] * 8, [100] * 8, actions=[div])
    r = run(m, days, initial_target=1.0, decisions=pd.Series({days[1]: 0.0}))
    assert r.orders["side"].tolist() == ["BUY", "SELL"] and r.daily["units"].iloc[-1] == 0


def test_band_skips_small_changes_but_not_the_initial_build():
    m, days = market([100] * 6, [100] * 6)
    r = run(m, days, initial_target=0.5, no_trade_band=0.05,
            decisions=pd.Series({days[1]: 0.52, days[3]: 0.30}))
    assert (r.events["type"] == "BAND_SKIP").sum() == 1
    assert r.orders["date"].tolist() == [days[0], days[4]]


def test_costs_slippage_and_identity_with_fees():
    m, days = market([100, 102, 101, 103], [101, 101, 102, 104])
    r = run(m, days, costs=FlatFee(), initial_target=1.0, decisions=pd.Series({days[1]: 0.5}),
            slippage_bps=10)
    first, second = r.orders.iloc[0], r.orders.iloc[1]
    assert first["fill_price"] == pytest.approx(100.1) and first["commission"] == 20
    assert second["tax"] == round(second["fill_price"] * second["quantity"] * 0.001)
    assert (r.daily["settled_cash"] >= 0).all() and np.allclose(r.daily["identity_residual"], 0)


def test_fractional_instrument_uses_its_own_step():
    coin = Instrument("X:COIN", "X", "crypto_spot", "USDT", quantity_step="0.001")
    m, days = market([3000.0] * 3, [3000.0] * 3)
    r = run(m, days, instrument=coin, initial_target=1.0)
    assert r.daily["units"].iloc[0] == pytest.approx(3.333)  # 10,000 / 3,000 floored to 0.001
