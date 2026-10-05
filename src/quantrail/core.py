"""Core types shared by every layer: provenance, declarations, trust flags, instruments, money.

Nothing here knows about a particular market. See docs/adr/0002 and docs/adr/0003.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum

UNKNOWN = "unknown"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True)
class TrustFlag:
    """A machine-readable caveat that travels with a dataset into every result."""

    code: str
    severity: Severity
    message: str


@dataclass(frozen=True)
class TrustReport:
    flags: tuple[TrustFlag, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.flags

    @property
    def blocking(self) -> tuple[TrustFlag, ...]:
        return tuple(f for f in self.flags if f.severity is Severity.BLOCKING)

    def merge(self, *others: TrustReport) -> TrustReport:
        seen = {f.code: f for f in self.flags}
        for other in others:
            for flag in other.flags:
                seen.setdefault(flag.code, flag)
        return TrustReport(tuple(seen.values()))

    def render(self) -> str:
        if self.clean:
            return "Trust report: no caveats recorded."
        marks = {Severity.INFO: "i", Severity.WARNING: "!", Severity.BLOCKING: "x"}
        lines = ["Trust report:"]
        lines += [f"  [{marks[f.severity]}] {f.code}: {f.message}" for f in self.flags]
        return "\n".join(lines)


@dataclass(frozen=True)
class Provenance:
    """Where data came from and under what terms. Every field may be unknown (ADR 0002)."""

    source: str = UNKNOWN
    license: str = UNKNOWN
    terms_url: str | None = None
    retrieved_at: str | None = None
    notes: str = ""

    @property
    def license_known(self) -> bool:
        return self.license.strip().lower() != UNKNOWN and bool(self.license.strip())

    def trust(self) -> TrustReport:
        flags = []
        if self.source.strip().lower() in {"", UNKNOWN}:
            flags.append(TrustFlag("SOURCE_UNKNOWN", Severity.WARNING,
                                   "Data source is not recorded."))
        if not self.license_known:
            flags.append(TrustFlag("LICENCE_UNKNOWN", Severity.WARNING,
                                   "Licence is unknown: private research only; "
                                   "exporting or sharing requires an explicit acknowledgement."))
        return TrustReport(tuple(flags))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Provenance:
        return cls(**data)


class PriceBasis(StrEnum):
    RAW = "raw"
    SPLIT_ADJUSTED = "split_adjusted"
    TOTAL_RETURN = "total_return"
    UNKNOWN = UNKNOWN


@dataclass(frozen=True)
class Declaration:
    """What a dataset claims about itself.

    availability: when each row becomes known, e.g. "close" (after the session close),
    "column:published_at" (per-row timestamp column) or "unknown".
    corporate_actions: True if dividend/split events are supplied, False if known to be
    absent, None if not stated.
    """

    price_basis: PriceBasis = PriceBasis.UNKNOWN
    availability: str = UNKNOWN
    corporate_actions: bool | None = None

    def trust(self) -> TrustReport:
        flags = []
        if self.price_basis is PriceBasis.UNKNOWN:
            flags.append(TrustFlag(
                "PRICE_BASIS_UNKNOWN", Severity.WARNING,
                "Prices may be raw or adjusted; accounting uses a conservative approximation."))
        if self.price_basis is not PriceBasis.RAW or self.corporate_actions is not True:
            flags.append(TrustFlag(
                "ACCOUNTING_APPROXIMATE", Severity.WARNING,
                "Ledger-accurate accounting needs raw prices plus dividend and split events."))
        if self.availability.strip().lower() in {"", UNKNOWN}:
            flags.append(TrustFlag(
                "AVAILABILITY_UNVERIFIED", Severity.WARNING,
                "Availability time is not declared; results may use data before it was known."))
        return TrustReport(tuple(flags))

    def to_dict(self) -> dict:
        return {"price_basis": self.price_basis.value, "availability": self.availability,
                "corporate_actions": self.corporate_actions}

    @classmethod
    def from_dict(cls, data: dict) -> Declaration:
        return cls(PriceBasis(data["price_basis"]), data["availability"], data["corporate_actions"])


def to_decimal(value, name: str = "value") -> Decimal:
    """Exact conversion; floats go through str() so 0.1 stays 0.1."""
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError(f"{name} is not a number: {value!r}") from error
    if not result.is_finite():
        raise ValueError(f"{name} must be finite: {value!r}")
    return result


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        object.__setattr__(self, "amount", to_decimal(self.amount, "amount"))
        if not self.currency or self.currency != self.currency.upper():
            raise ValueError(f"currency must be an upper-case code: {self.currency!r}")

    def _same(self, other: Money) -> None:
        if not isinstance(other, Money) or other.currency != self.currency:
            raise ValueError("Money arithmetic needs the same currency; convert explicitly first.")

    def __add__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)


@dataclass(frozen=True)
class Instrument:
    """A tradable thing. Quantity rules belong to the instrument, not to the core.

    quantity_step: smallest increment (1 share, 1000 shares, 0.00001 BTC).
    min_quantity: smallest order size; defaults to one step.
    """

    id: str
    venue: str
    asset_class: str
    quote_currency: str
    quantity_step: Decimal = Decimal("1")
    min_quantity: Decimal | None = None
    price_tick: Decimal | None = None
    attributes: dict = field(default_factory=dict, compare=False)

    def __post_init__(self):
        step = to_decimal(self.quantity_step, "quantity_step")
        if step <= 0:
            raise ValueError("quantity_step must be positive")
        object.__setattr__(self, "quantity_step", step)
        minimum = step if self.min_quantity is None else to_decimal(self.min_quantity, "min_quantity")
        if minimum < step or (minimum / step) % 1 != 0:
            raise ValueError("min_quantity must be a positive multiple of quantity_step")
        object.__setattr__(self, "min_quantity", minimum)

    def validate_quantity(self, quantity) -> Decimal:
        """Return the quantity as Decimal if it is on the step grid, else raise."""
        q = to_decimal(quantity, "quantity")
        if q < 0:
            raise ValueError("quantity must be non-negative")
        if (q / self.quantity_step) % 1 != 0:
            raise ValueError(f"{q} is not a multiple of {self.quantity_step} for {self.id}")
        if 0 < q < self.min_quantity:
            raise ValueError(f"{q} is below the minimum {self.min_quantity} for {self.id}")
        return q

    def floor_quantity(self, quantity) -> Decimal:
        """Largest valid quantity not above `quantity` (0 if below the minimum)."""
        q = to_decimal(quantity, "quantity")
        if q <= 0:
            return Decimal("0")
        floored = (q // self.quantity_step) * self.quantity_step
        return floored if floored >= self.min_quantity else Decimal("0")
