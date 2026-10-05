"""QuantRail: quantitative research you can trust.

Importing QuantRail never downloads data, writes files or contacts a broker.
"""

from .backtest import BacktestResult, backtest
from .core import UNKNOWN, Declaration, Instrument, Money, PriceBasis, Provenance, TrustReport
from .datasets import export_dataset, ingest, list_versions, load_dataset
from .research.trials import TrialRegistry

__version__ = "0.0.1"

__all__ = [
    "UNKNOWN", "BacktestResult", "Declaration", "Instrument", "Money", "PriceBasis", "Provenance",
    "TrialRegistry", "TrustReport", "backtest", "export_dataset", "ingest", "list_versions",
    "load_dataset",
]
