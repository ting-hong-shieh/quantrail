"""One-call backtest from an ingested dataset, with the trust report attached.

This adapter turns a dataset produced by `ingest()` into the engine's tables and adds
the caveats that come from the data itself:

- no open prices: fills use the next session's close (EXECUTION_NEXT_CLOSE_PROXY);
- sessions inferred from the price dates (CALENDAR_FROM_PRICES): exchange holidays and
  suspensions without a row cannot be told apart;
- total-return prices together with dividend events would count dividends twice and
  are refused.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .core import Instrument, PriceBasis, Severity, TrustFlag, TrustReport
from .datasets import Dataset
from .engine import Result, run_target_weights
from .stats import metrics

ACTION_COLUMNS = {"action_id", "action_type", "effective_date", "ex_date", "payment_date",
                  "split_new_per_old", "cash_per_entitled_unit"}


@dataclass
class BacktestResult:
    result: Result
    trust: TrustReport
    summary: dict

    @property
    def daily(self) -> pd.DataFrame:
        return self.result.daily

    @property
    def orders(self) -> pd.DataFrame:
        return self.result.orders

    @property
    def events(self) -> pd.DataFrame:
        return self.result.events

    def report(self) -> str:
        lines = [self.trust.render(), "", "Summary:"]
        for key in ("start", "end", "final_nav", "cagr", "annual_volatility", "sharpe", "max_drawdown"):
            value = self.summary[key]
            lines.append(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")
        return "\n".join(lines)


def _sessions(n: int):
    """Settlement helper: T+n on the dataset's own sessions."""
    def make(sessions):
        ordered = sorted(sessions)

        def settle(day):
            if n == 0:
                return day
            future = [s for s in ordered if s > day]
            if len(future) < n:
                # Beyond the data: settle n calendar days later; affects only the last sessions.
                return day + pd.Timedelta(n, unit="D").to_pytimedelta()
            return future[n - 1]
        return settle
    return make


def backtest(dataset: Dataset, *, instrument: Instrument, costs, capital, initial_target=1.0,
             decisions=None, no_trade_band=0.0, slippage_bps=0.0, settlement_lag=0,
             start=None, end=None) -> BacktestResult:
    """Run a target-weight backtest of one instrument on an ingested dataset."""
    prices = dataset.tables["prices"]
    if prices["instrument"].nunique() != 1:
        raise ValueError("backtest() handles one instrument per dataset for now.")
    flags = []
    table = pd.DataFrame({"session_date": pd.to_datetime(prices["date"]),
                          "close": prices["close"].astype(float),
                          "quote_valid": prices["quote_valid"].astype(bool)})
    if "open" in prices:
        table["open"] = prices["open"].astype(float)
    else:
        table["open"] = table["close"]
        flags.append(TrustFlag("EXECUTION_NEXT_CLOSE_PROXY", Severity.WARNING,
                               "No open prices: orders fill at the next session's close."))
    calendar = pd.DataFrame({"session_date": table["session_date"], "asset_tradable": True, "reason": ""})
    flags.append(TrustFlag("CALENDAR_FROM_PRICES", Severity.INFO,
                           "Sessions are inferred from price dates; missing sessions cannot be detected."))

    actions = dataset.tables.get("corporate_actions")
    if actions is None:
        actions = pd.DataFrame(columns=sorted(ACTION_COLUMNS))
    else:
        missing = ACTION_COLUMNS - set(actions.columns)
        if missing:
            raise ValueError(f"corporate_actions is missing columns: {sorted(missing)}")
        actions = actions.copy()
        for column in ("effective_date", "ex_date", "payment_date"):
            actions[column] = pd.to_datetime(actions[column])
        has_dividends = (actions["action_type"] == "CASH_DISTRIBUTION").any()
        if dataset.declaration.price_basis is PriceBasis.TOTAL_RETURN and has_dividends:
            raise ValueError("Total-return prices already include dividends; supplying dividend events "
                             "too would count them twice.")

    first, last = table["session_date"].min(), table["session_date"].max()
    start, end = pd.Timestamp(start) if start else first, pd.Timestamp(end) if end else last
    sessions = [d.date() for d in table["session_date"]]
    result = run_target_weights(
        instrument=instrument, costs=costs, settle=_sessions(settlement_lag)(sessions),
        prices=table, calendar=calendar, actions=actions, start=start, end=end, capital=capital,
        initial_target=initial_target, decisions=decisions, no_trade_band=no_trade_band,
        slippage_bps=slippage_bps, label=dataset.dataset_id)
    trust = dataset.trust.merge(TrustReport(tuple(flags)))
    return BacktestResult(result, trust, metrics.summary(result.daily["nav"], float(capital)))
