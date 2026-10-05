"""Opt-in check against a private reference simulation (data is not distributed).

Set QUANTRAIL_REF_DATA to a curated Taiwan equity dataset folder (prices_raw, calendar,
corporate_actions parquet files) and QUANTRAIL_REF_RUN to a reference run folder with
daily.parquet, summary.json and decisions.parquet. Optional QUANTRAIL_REF_BAND and
QUANTRAIL_REF_BPS describe the reference run. Skipped when the variables are unset.
"""

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from quantrail.engine import run_target_weights
from quantrail.markets import tw_equity as tw

DATA, RUN = os.environ.get("QUANTRAIL_REF_DATA"), os.environ.get("QUANTRAIL_REF_RUN")


@pytest.mark.skipif(not (DATA and RUN), reason="private reference data not configured")
def test_daily_nav_matches_reference_exactly():
    data, run = Path(DATA), Path(RUN)
    prices = pd.read_parquet(data / "prices_raw.parquet")
    calendar = pd.read_parquet(data / "calendar.parquet")
    actions = pd.read_parquet(data / "corporate_actions.parquet")
    ref = pd.read_parquet(run / "daily.parquet")
    summary = json.loads((run / "summary.json").read_text())
    decisions_path = run / "decisions.parquet"
    decisions = pd.read_parquet(decisions_path)["target"] if decisions_path.exists() else None
    end = ref.index[-1]
    sessions = [d.date() for d in calendar["session_date"]]
    result = run_target_weights(
        instrument=tw.share("0050"), costs=tw.TaiwanEquityCosts(),
        settle=lambda d: tw.settlement_date(d, sessions),
        prices=prices[prices.session_date <= end], calendar=calendar[calendar.session_date <= end],
        actions=actions[actions.effective_date <= end], start=ref.index[0], end=end,
        capital=summary["capital"], initial_target=summary.get("initial_target", 1.0), decisions=decisions,
        no_trade_band=float(os.environ.get("QUANTRAIL_REF_BAND", 0)),
        slippage_bps=float(os.environ.get("QUANTRAIL_REF_BPS", 5)))
    assert len(result.daily) == len(ref)
    assert (result.daily["nav"] - ref["nav"]).abs().max() == 0
