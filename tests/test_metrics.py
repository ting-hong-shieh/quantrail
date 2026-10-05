import math

import pandas as pd
import pytest

from quantrail.stats import metrics as m

DAYS = pd.bdate_range("2024-01-01", periods=4)
NAV = pd.Series([101.0, 99.99, 102.0, 102.0], index=DAYS)


def test_returns_start_from_capital():
    r = m.daily_returns(NAV, 100.0)
    assert list(r.round(10)) == [0.01, -0.01, round(102 / 99.99 - 1, 10), 0.0]


def test_drawdown_and_underwater_include_starting_capital():
    nav = pd.Series([90.0, 95.0, 110.0], index=pd.to_datetime(["2024-01-01", "2024-01-10", "2024-01-20"]))
    assert m.max_drawdown(nav, 100.0) == pytest.approx(-0.10)
    assert m.longest_underwater_days(nav, 100.0) == 9  # below 100 from Jan 1 to Jan 10


def test_cagr_uses_calendar_days():
    nav = pd.Series([100.0, 121.0], index=pd.to_datetime(["2020-01-01", "2021-12-31"]))
    years = (pd.Timestamp("2021-12-31") - pd.Timestamp("2020-01-01")).days / 365.25
    assert m.cagr(nav, 100.0) == pytest.approx(1.21 ** (1 / years) - 1)


def test_brain_style_definitions():
    traded = pd.Series({DAYS[0]: 100.0, DAYS[2]: 50.0})
    out = m.brain_style(NAV, traded, 100.0)
    r = pd.Series([0.01, -0.01, 102 / 99.99 - 1, 0.0])
    assert out["sharpe"] == pytest.approx(r.mean() / r.std(ddof=1) * math.sqrt(252))
    assert out["turnover"] == pytest.approx((100 / 100 + 50 / 99.99) / 4)
    assert out["returns"] == pytest.approx(r.mean() * 252)
    assert out["fitness"] == pytest.approx(out["sharpe"] * math.sqrt(abs(out["returns"])
                                                                    / max(out["turnover"], 0.125)))
    assert out["margin_permyriad"] == pytest.approx(2.0 / 150 * 1e4)
    assert out["drawdown"] == pytest.approx(1 - 99.99 / 101)


def test_brain_style_without_trades():
    out = m.brain_style(NAV, pd.Series(dtype=float), 100.0)
    assert out["turnover"] == 0 and math.isnan(out["margin_permyriad"])


def test_invalid_nav_is_refused():
    with pytest.raises(ValueError):
        m.daily_returns(pd.Series([1.0, -1.0], index=DAYS[:2]), 1.0)
    with pytest.raises(ValueError):
        m.daily_returns(pd.Series([1.0, 2.0]), 1.0)
