"""A market-neutral cost model for users without a dedicated market module."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..core import to_decimal


@dataclass(frozen=True)
class ProportionalCosts:
    """Commission as a rate with an optional minimum, plus an optional tax on sells. No rounding."""

    commission_rate: Decimal = Decimal("0")
    minimum_fee: Decimal = Decimal("0")
    sell_tax_rate: Decimal = Decimal("0")

    def __post_init__(self):
        for name in ("commission_rate", "minimum_fee", "sell_tax_rate"):
            value = to_decimal(getattr(self, name), name)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
            object.__setattr__(self, name, value)

    def fees(self, instrument, side, quantity, price, day) -> tuple[Decimal, Decimal]:
        value = to_decimal(quantity) * to_decimal(price)
        commission = max(self.minimum_fee, value * self.commission_rate)
        tax = value * self.sell_tax_rate if side == "SELL" else Decimal("0")
        return commission, tax
