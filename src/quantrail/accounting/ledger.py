"""Multi-currency ledger with Decimal quantities and settlement-dated cash.

Positions change when a fill is booked; cash changes only when an obligation settles.
Receivables (unsettled sales, declared dividends) count towards net asset value but
are never spendable. Buying power is the lowest projected cash balance over future
settlement dates, so an order can never be funded by money that arrives later.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..core import Instrument, to_decimal

ZERO = Decimal("0")


class InsufficientCash(RuntimeError):
    """An order or settlement would need cash the account does not have."""


@dataclass(frozen=True)
class Obligation:
    settles_on: date
    currency: str
    amount: Decimal  # positive: receivable, negative: payable
    reference: str


@dataclass(frozen=True)
class Fill:
    instrument: Instrument
    side: str  # "BUY" or "SELL"
    quantity: Decimal
    price: Decimal
    trade_date: date
    settles_on: date
    commission: Decimal = ZERO
    tax: Decimal = ZERO
    reference: str = ""

    @property
    def value(self) -> Decimal:
        return self.quantity * self.price

    @property
    def cash_delta(self) -> Decimal:
        fees = self.commission + self.tax
        return -(self.value + fees) if self.side == "BUY" else self.value - fees


@dataclass(frozen=True)
class CashSnapshot:
    currency: str
    settled: Decimal
    receivable: Decimal
    payable: Decimal

    @property
    def net(self) -> Decimal:
        return self.settled + self.receivable - self.payable


class Ledger:
    def __init__(self, cash: dict[str, object]):
        self._cash = {ccy: to_decimal(v, f"cash[{ccy}]") for ccy, v in cash.items()}
        if any(v < 0 for v in self._cash.values()):
            raise ValueError("Initial cash must be non-negative.")
        self._positions: dict[str, Decimal] = defaultdict(lambda: ZERO)
        self._pending: dict[str, Obligation] = {}
        self.journal: list[dict] = []

    # Queries -----------------------------------------------------------------
    def position(self, instrument_id: str) -> Decimal:
        return self._positions.get(instrument_id, ZERO)

    def snapshot(self, currency: str) -> CashSnapshot:
        pending = [o for o in self._pending.values() if o.currency == currency]
        return CashSnapshot(currency, self._cash.get(currency, ZERO),
                            sum((o.amount for o in pending if o.amount > 0), ZERO),
                            -sum((o.amount for o in pending if o.amount < 0), ZERO))

    def buying_power(self, currency: str) -> Decimal:
        """Lowest projected settled cash over the pending settlement dates."""
        projected = lowest = self._cash.get(currency, ZERO)
        by_date: dict[date, Decimal] = defaultdict(lambda: ZERO)
        for o in self._pending.values():
            if o.currency == currency:
                by_date[o.settles_on] += o.amount
        for day in sorted(by_date):
            projected += by_date[day]
            lowest = min(lowest, projected)
        return lowest

    # Events ------------------------------------------------------------------
    def _add_obligation(self, obligation: Obligation) -> None:
        if obligation.reference in self._pending:
            raise ValueError(f"Duplicate obligation reference {obligation.reference}")
        self._pending[obligation.reference] = obligation

    def book_fill(self, fill: Fill) -> None:
        q = fill.instrument.validate_quantity(fill.quantity)
        if q == 0:
            raise ValueError("A fill needs a positive quantity.")
        if fill.side not in {"BUY", "SELL"}:
            raise ValueError(f"Unknown side {fill.side!r}")
        currency = fill.instrument.quote_currency
        if fill.side == "SELL" and q > self.position(fill.instrument.id):
            raise ValueError("Sell exceeds position; short selling is not modelled.")
        if fill.side == "BUY" and -fill.cash_delta > self.buying_power(currency):
            raise InsufficientCash(f"Buy of {-fill.cash_delta} {currency} exceeds buying power.")
        self._positions[fill.instrument.id] += q if fill.side == "BUY" else -q
        self._add_obligation(Obligation(fill.settles_on, currency, fill.cash_delta, f"fill:{fill.reference}"))
        self.journal.append({"type": "FILL", "date": fill.trade_date, "instrument": fill.instrument.id,
                             "side": fill.side, "quantity": q, "price": fill.price,
                             "commission": fill.commission, "tax": fill.tax, "settles_on": fill.settles_on})

    def entitle_cash_dividend(self, instrument: Instrument, per_unit, ex_date: date, payment_date: date,
                              reference: str) -> Decimal:
        """Entitlement on units held at the close before ex_date; cash arrives on payment_date."""
        amount = self.position(instrument.id) * to_decimal(per_unit, "per_unit")
        if amount > 0:
            self._add_obligation(Obligation(payment_date, instrument.quote_currency, amount,
                                            f"div:{reference}"))
        self.journal.append({"type": "DIVIDEND_ENTITLEMENT", "date": ex_date, "instrument": instrument.id,
                             "units": self.position(instrument.id), "per_unit": per_unit, "amount": amount,
                             "payment_date": payment_date})
        return amount

    def split(self, instrument: Instrument, new_per_old, effective: date) -> Decimal:
        ratio = to_decimal(new_per_old, "split ratio")
        if ratio <= 0:
            raise ValueError("Split ratio must be positive.")
        old = self.position(instrument.id)
        new = old * ratio
        if new != instrument.floor_quantity(new) and new != 0:
            raise ValueError("Fractional split entitlement needs an explicit cash-in-lieu event.")
        self._positions[instrument.id] = new
        self.journal.append({"type": "SPLIT", "date": effective, "instrument": instrument.id,
                             "before": old, "after": new})
        return new

    def settle_through(self, day: date) -> list[Obligation]:
        due = sorted((o for o in self._pending.values() if o.settles_on <= day),
                     key=lambda o: (o.settles_on, o.reference))
        projected = dict(self._cash)
        for o in due:
            projected[o.currency] = projected.get(o.currency, ZERO) + o.amount
            if projected[o.currency] < 0:
                raise InsufficientCash(f"Cannot settle {o.reference} on {o.settles_on}.")
        self._cash = projected
        for o in due:
            del self._pending[o.reference]
            self.journal.append({"type": "SETTLEMENT", "date": o.settles_on, "currency": o.currency,
                                 "amount": o.amount, "reference": o.reference})
        return due
