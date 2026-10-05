"""Taiwan listed equities and ETFs: costs, securities transaction tax, T+2 settlement.

Rounding follows the convention of the reference implementation this module was
validated against: commission and tax are rounded half-up to whole TWD, and the
commission has a minimum fee. Broker commission is a scenario, not a statutory rate.
Tax rates are effective-dated rules with their legal basis; a trade outside every
verified rule is refused rather than priced with a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from ..core import Instrument, to_decimal

CURRENCY = "TWD"
BOARD_LOT = Decimal("1000")
_ONE = Decimal("1")


def share(symbol: str, asset_class: str = "etf") -> Instrument:
    """Odd-lot granularity: whole shares."""
    return Instrument(f"TWSE:{symbol}", "TWSE", asset_class, CURRENCY, quantity_step=Decimal("1"))


def board_lot(symbol: str, asset_class: str = "etf") -> Instrument:
    """Board-lot granularity: multiples of 1,000 shares."""
    return Instrument(f"TWSE:{symbol}", "TWSE", asset_class, CURRENCY, quantity_step=BOARD_LOT)


@dataclass(frozen=True)
class TaxRule:
    asset_class: str
    side: str
    rate: Decimal
    legal_effective_from: date
    verified_from: date
    verified_through: date
    basis: str

    def covers(self, asset_class: str, side: str, day: date) -> bool:
        return (self.asset_class == asset_class and self.side == side
                and self.verified_from <= day <= self.verified_through)


# Securities Transaction Tax Act, Article 2(2); Ministry of Finance ruling 791182786
# classifies securities investment trust beneficiary certificates (incl. domestic
# equity ETFs) as "other government-approved securities" taxed at 1/1000 of the
# transaction value, paid by the seller. Verified for the window below on 2026-10-05.
# Bond ETFs (Article 2-1) and day-trade reductions (Article 2-2) are out of scope.
ETF_SELL_TAX_TW = TaxRule(
    asset_class="etf", side="SELL", rate=Decimal("0.001"),
    legal_effective_from=date(1993, 2, 1), verified_from=date(2013, 1, 2),
    verified_through=date(2026, 9, 30),
    basis="Securities Transaction Tax Act Art. 2(2); MOF ruling 791182786",
)


class UnverifiedTaxRule(LookupError):
    """No verified tax rule covers the trade; refuse rather than guess."""


@dataclass(frozen=True)
class TaiwanEquityCosts:
    commission_rate: Decimal = Decimal("0.001425")
    commission_discount: Decimal = Decimal("1")
    minimum_fee: Decimal = Decimal("20")
    tax_rules: tuple[TaxRule, ...] = (ETF_SELL_TAX_TW,)

    def __post_init__(self):
        for name in ("commission_rate", "commission_discount", "minimum_fee"):
            value = to_decimal(getattr(self, name), name)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
            object.__setattr__(self, name, value)

    @staticmethod
    def _round(value: Decimal) -> Decimal:
        return value.quantize(_ONE, rounding=ROUND_HALF_UP)

    def commission(self, value: Decimal) -> Decimal:
        return max(self.minimum_fee, self._round(value * self.commission_rate * self.commission_discount))

    def tax(self, instrument: Instrument, side: str, value: Decimal, day: date) -> Decimal:
        if side == "BUY":
            return Decimal("0")
        rules = [r for r in self.tax_rules if r.covers(instrument.asset_class, side, day)]
        if len(rules) != 1:
            raise UnverifiedTaxRule(
                f"No single verified {side} tax rule for {instrument.asset_class} on {day}.")
        return self._round(value * rules[0].rate)

    def fees(self, instrument: Instrument, side: str, quantity, price, day: date) -> tuple[Decimal, Decimal]:
        value = to_decimal(quantity) * to_decimal(price)
        return self.commission(value), self.tax(instrument, side, value, day)


def settlement_date(trade_date: date, sessions, lag: int = 2) -> date:
    """T+lag on exchange sessions."""
    future = sorted(d for d in sessions if d > trade_date)
    if len(future) < lag:
        raise LookupError("The calendar does not reach the settlement date.")
    return trade_date if lag == 0 else future[lag - 1]
