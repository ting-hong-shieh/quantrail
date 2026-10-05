from datetime import date
from decimal import Decimal

import pytest

from quantrail.accounting.ledger import Fill, InsufficientCash, Ledger
from quantrail.core import Instrument

ETF = Instrument("X:ETF", "X", "etf", "TWD")
D = Decimal


def buy(q, price, day, settles, ref, fee=0):
    return Fill(ETF, "BUY", D(q), D(price), day, settles, D(fee), D(0), ref)


def test_buying_power_ignores_money_that_arrives_later():
    ledger = Ledger({"TWD": 1000})
    ledger.book_fill(buy(5, 100, date(2024, 1, 2), date(2024, 1, 4), "a"))
    assert ledger.buying_power("TWD") == D(500)  # payable already committed
    ledger.book_fill(Fill(ETF, "SELL", D(5), D(100), date(2024, 1, 3), date(2024, 1, 5), D(0), D(0), "b"))
    assert ledger.buying_power("TWD") == D(500)  # sale proceeds are not spendable yet
    with pytest.raises(InsufficientCash):
        ledger.book_fill(buy(6, 100, date(2024, 1, 3), date(2024, 1, 5), "c"))


def test_settlement_moves_cash_and_snapshot_balances():
    ledger = Ledger({"TWD": 1000})
    ledger.book_fill(buy(5, 100, date(2024, 1, 2), date(2024, 1, 4), "a", fee=20))
    snap = ledger.snapshot("TWD")
    assert (snap.settled, snap.payable, snap.net) == (D(1000), D(520), D(480))
    ledger.settle_through(date(2024, 1, 4))
    assert ledger.snapshot("TWD").settled == D(480)


def test_dividend_is_receivable_until_paid():
    ledger = Ledger({"TWD": 0})
    ledger._positions[ETF.id] = D(100)
    assert ledger.entitle_cash_dividend(ETF, "1.5", date(2024, 1, 2), date(2024, 1, 20), "d") == D(150)
    assert ledger.buying_power("TWD") == 0 and ledger.snapshot("TWD").receivable == D(150)
    ledger.settle_through(date(2024, 1, 20))
    assert ledger.snapshot("TWD").settled == D(150)


def test_split_keeps_value_and_refuses_fractional_entitlement():
    ledger = Ledger({"TWD": 0})
    ledger._positions[ETF.id] = D(3)
    assert ledger.split(ETF, 4, date(2025, 6, 18)) == D(12)
    with pytest.raises(ValueError, match="cash-in-lieu"):
        ledger.split(ETF, "0.1", date(2025, 6, 19))  # 12 x 0.1 = 1.2 units


def test_no_short_selling_and_cash_is_per_currency():
    ledger = Ledger({"TWD": 100, "USD": 50})
    with pytest.raises(ValueError, match="short"):
        ledger.book_fill(Fill(ETF, "SELL", D(1), D(1), date(2024, 1, 2), date(2024, 1, 4), reference="s"))
    assert ledger.buying_power("USD") == D(50) and ledger.buying_power("JPY") == D(0)
