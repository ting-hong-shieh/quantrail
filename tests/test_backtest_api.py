from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

import quantrail as qr
from quantrail.markets.generic import ProportionalCosts

COIN = qr.Instrument("X:COIN", "X", "crypto_spot", "USD", quantity_step="0.0001")


def closes(n=60):
    days = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame({"date": days, "close": 100 * np.exp(np.cumsum(np.full(n, 0.001)))})


def test_close_only_data_runs_and_says_so(tmp_path):
    ds = qr.ingest(closes(), root=tmp_path, dataset_id="mine", version="v1", instrument="X:COIN")
    result = qr.backtest(ds, instrument=COIN, costs=ProportionalCosts(), capital=10_000)
    codes = {f.code for f in result.trust.flags}
    assert {"LICENCE_UNKNOWN", "EXECUTION_NEXT_CLOSE_PROXY", "CALENDAR_FROM_PRICES"} <= codes
    # The initial build fills at the first session's price (its close, as there is no open),
    # rounded to the 0.0001 price grid.
    assert result.orders["fill_price"].iloc[0] == pytest.approx(closes()["close"].iloc[0], abs=1e-4)
    assert np.allclose(result.daily["identity_residual"], 0)
    assert "Trust report:" in result.report() and "cagr" in result.report()


def test_total_return_prices_with_dividend_events_are_refused(tmp_path):
    events = pd.DataFrame({"action_id": ["d1"], "action_type": ["CASH_DISTRIBUTION"],
                           "effective_date": ["2024-01-10"], "ex_date": ["2024-01-10"],
                           "payment_date": ["2024-01-20"], "split_new_per_old": [np.nan],
                           "cash_per_entitled_unit": [1.0]})
    ds = qr.ingest(closes(), root=tmp_path, dataset_id="tr", version="v1", instrument="X:COIN",
                   declaration=qr.Declaration(qr.PriceBasis.TOTAL_RETURN, "close"),
                   corporate_actions=events)
    with pytest.raises(ValueError, match="twice"):
        qr.backtest(ds, instrument=COIN, costs=ProportionalCosts(), capital=10_000)


def test_proportional_costs():
    costs = ProportionalCosts(commission_rate="0.001", minimum_fee=1, sell_tax_rate="0.002")
    assert costs.fees(COIN, "BUY", 10, 50, None) == (Decimal(1), Decimal(0))       # 0.5 -> minimum 1
    assert costs.fees(COIN, "SELL", 100, 50, None) == (Decimal("5"), Decimal("10"))
