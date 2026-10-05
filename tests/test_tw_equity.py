from datetime import date
from decimal import Decimal

import pytest

from quantrail.markets import tw_equity as tw

D = Decimal
ETF = tw.share("0050")


def test_commission_minimum_and_half_up_rounding():
    costs = tw.TaiwanEquityCosts()
    assert costs.commission(D(10_000)) == D(20)          # 14.25 -> minimum 20
    assert costs.commission(D(1_000_000)) == D(1425)     # 1425.0
    assert costs.commission(D(1_403_509)) == D(2000)     # 1999.99... -> 2000
    assert tw.TaiwanEquityCosts(commission_discount="0.6").commission(D(1_000_000)) == D(855)


def test_sell_tax_only_within_the_verified_window():
    costs = tw.TaiwanEquityCosts()
    assert costs.tax(ETF, "BUY", D(1_000_000), date(2020, 1, 2)) == 0
    assert costs.tax(ETF, "SELL", D(1_000_500), date(2020, 1, 2)) == D(1001)  # 1000.5 -> 1001
    with pytest.raises(tw.UnverifiedTaxRule):
        costs.tax(ETF, "SELL", D(1000), date(2026, 10, 5))
    with pytest.raises(tw.UnverifiedTaxRule):
        costs.tax(tw.share("2330", asset_class="stock"), "SELL", D(1000), date(2020, 1, 2))


def test_t_plus_two_on_exchange_sessions():
    sessions = [date(2024, 1, d) for d in (2, 3, 4, 5, 8)]
    assert tw.settlement_date(date(2024, 1, 4), sessions) == date(2024, 1, 8)
    with pytest.raises(LookupError):
        tw.settlement_date(date(2024, 1, 5), sessions)


def test_share_and_board_lot_instruments():
    assert tw.board_lot("0050").floor_quantity(2999) == D(2000)
    assert ETF.validate_quantity(1) == D(1)
