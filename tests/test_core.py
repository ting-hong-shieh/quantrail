from decimal import Decimal

import pytest

from quantrail.core import (
    UNKNOWN,
    Declaration,
    Instrument,
    Money,
    PriceBasis,
    Provenance,
    Severity,
    TrustReport,
)


def codes(report: TrustReport) -> set[str]:
    return {f.code for f in report.flags}


class TestProvenance:
    def test_defaults_are_unknown_and_flagged_not_rejected(self):
        p = Provenance()
        assert p.source == UNKNOWN and p.license == UNKNOWN
        assert codes(p.trust()) == {"SOURCE_UNKNOWN", "LICENCE_UNKNOWN"}
        assert all(f.severity is Severity.WARNING for f in p.trust().flags)

    def test_known_licence_is_clean(self):
        p = Provenance(source="Open data portal", license="CC-BY-4.0")
        assert p.license_known and p.trust().clean

    def test_round_trip(self):
        p = Provenance(source="s", license="l", terms_url="https://example.test/terms")
        assert Provenance.from_dict(p.to_dict()) == p


class TestDeclaration:
    def test_raw_prices_with_events_and_availability_are_clean(self):
        d = Declaration(PriceBasis.RAW, "close", corporate_actions=True)
        assert d.trust().clean

    def test_adjusted_prices_mean_approximate_accounting(self):
        d = Declaration(PriceBasis.TOTAL_RETURN, "close", corporate_actions=False)
        assert codes(d.trust()) == {"ACCOUNTING_APPROXIMATE"}

    def test_everything_unknown(self):
        assert codes(Declaration().trust()) == {
            "PRICE_BASIS_UNKNOWN", "ACCOUNTING_APPROXIMATE", "AVAILABILITY_UNVERIFIED"}

    def test_round_trip(self):
        d = Declaration(PriceBasis.RAW, "column:published_at", None)
        assert Declaration.from_dict(d.to_dict()) == d


class TestTrustReport:
    def test_merge_deduplicates_by_code_and_renders(self):
        merged = Provenance().trust().merge(Provenance().trust(), Declaration().trust())
        assert len(merged.flags) == 5
        text = merged.render()
        assert "LICENCE_UNKNOWN" in text and text.startswith("Trust report:")


class TestMoney:
    def test_floats_are_converted_exactly(self):
        assert Money(0.1, "TWD").amount == Decimal("0.1")

    def test_cross_currency_arithmetic_is_refused(self):
        with pytest.raises(ValueError, match="same currency"):
            Money(1, "USD") + Money(1, "TWD")

    def test_non_finite_is_refused(self):
        with pytest.raises(ValueError):
            Money(float("nan"), "TWD")


class TestInstrument:
    def test_share_lot_and_crypto_steps(self):
        share = Instrument("TWSE:0050", "TWSE", "etf", "TWD")
        lot = Instrument("TWSE:0050@lot", "TWSE", "etf", "TWD", quantity_step=1000)
        btc = Instrument("BINANCE:BTCUSDT", "BINANCE", "crypto_spot", "USDT",
                         quantity_step="0.00001", min_quantity="0.0001")
        assert share.validate_quantity(15) == Decimal("15")
        assert lot.floor_quantity(2999) == Decimal("2000")
        assert btc.validate_quantity("0.01234") == Decimal("0.01234")
        assert btc.floor_quantity("0.00009") == Decimal("0")
        with pytest.raises(ValueError, match="multiple"):
            lot.validate_quantity(1500)
        with pytest.raises(ValueError, match="below the minimum"):
            btc.validate_quantity("0.00005")

    def test_min_quantity_must_sit_on_the_grid(self):
        with pytest.raises(ValueError):
            Instrument("X", "V", "c", "USD", quantity_step="0.1", min_quantity="0.15")
