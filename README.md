<p align="center">
  <img src="https://raw.githubusercontent.com/ting-hong-shieh/quantrail/main/assets/brand/quantrail-badge.svg" width="104" alt="QuantRail logo">
</p>

<h1 align="center">QuantRail</h1>

<p align="center"><b>Every backtest makes assumptions. QuantRail makes them visible.</b><br>
Data governance · ledger-accurate simulation</p>

<p align="center">
  <a href="https://pypi.org/project/quantrail/"><img src="https://img.shields.io/pypi/v/quantrail?color=0F766E&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://github.com/ting-hong-shieh/quantrail/actions/workflows/ci.yml"><img src="https://github.com/ting-hong-shieh/quantrail/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white" alt="Python 3.11 | 3.12 | 3.13">
  <a href="https://github.com/ting-hong-shieh/quantrail/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-0F766E" alt="Apache-2.0"></a>
  <img src="https://img.shields.io/badge/status-pre--alpha-F59E0B" alt="Status: pre-alpha">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

<p align="center">
  <a href="https://github.com/ting-hong-shieh/quantrail/blob/main/README.zh-TW.md">繁體中文</a> ·
  <a href="https://github.com/ting-hong-shieh/quantrail/blob/main/docs/architecture.md">Architecture</a> ·
  <a href="https://github.com/ting-hong-shieh/quantrail/tree/main/docs/adr/">Decisions</a> ·
  <a href="https://github.com/ting-hong-shieh/quantrail/blob/main/CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/ting-hong-shieh/quantrail/main/assets/trust-report.svg" width="820" alt="A QuantRail result opens with a trust report listing recorded caveats">
</p>

> **Status:** early development (v0.x); APIs will change. Nothing here is investment advice.

## Why QuantRail?

A backtest can be hard to assess when:

- positions are multiplied by adjusted returns, so dividends, splits and settlement may be approximated or double-counted;
- the data version, licence or availability time a result depended on is not recorded;
- the many variants tried before the "winner" are forgotten, so overfitting goes unmeasured.

QuantRail is built around two pillars:

| Pillar | What you get |
| --- | --- |
| **Data governance** | Versioned, hashed datasets with manifests: source, licence, price basis, declared availability and quality checks. Availability is declaration text; rows are not filtered by when they became available. "Unknown" is allowed and reported, never hidden. |
| **Ledger-accurate simulation** | Raw prices plus explicit events (fees, taxes, dividends, splits, settlement). The engine records a daily NAV identity residual; it does not reject a run when the residual exceeds a tolerance. |

**Also included:** an append-only trial registry, paired block bootstrap, Holm correction, deflated Sharpe ratio and probability of backtest overfitting (PBO). Research design, rule freezing and out-of-sample policy are the responsibility of your own research workflow; QuantRail does not freeze experiment contracts or seal holdout data.

## Quickstart

```python
import tempfile

import numpy as np
import pandas as pd

import quantrail as qr
from quantrail.markets.generic import ProportionalCosts

# Any price table you have: only a date and a close are required.
days = pd.bdate_range("2024-01-01", periods=250)
returns = np.random.default_rng(0).normal(0.0004, 0.01, 250)
prices = pd.DataFrame({"date": days, "close": 100 * np.exp(np.cumsum(returns))})

store = tempfile.mkdtemp()
data = qr.ingest(prices, root=store, dataset_id="my-prices", version="v1", instrument="X:ABC")

asset = qr.Instrument("X:ABC", "X", "equity", "USD")
result = qr.backtest(data, instrument=asset, capital=10_000,
                     costs=ProportionalCosts(commission_rate="0.001"))
print(result.report())
```

The report starts with caveats about undeclared metadata and assumptions used by the backtest:

```text
Trust report:
  [!] SOURCE_UNKNOWN: Data source is not recorded.
  [!] LICENCE_UNKNOWN: Licence is unknown: private research only; ...
  [!] PRICE_BASIS_UNKNOWN: Prices may be raw or adjusted; ...
  [!] ACCOUNTING_APPROXIMATE: Ledger-accurate accounting needs raw prices plus dividend and split events.
  [!] AVAILABILITY_UNVERIFIED: Availability time is not declared; ...
  [!] NO_OPEN_PRICES: No open prices: next-open execution cannot be modelled.
  [!] EXECUTION_NEXT_CLOSE_PROXY: No open prices: orders fill at the next session's close.
  [i] CALENDAR_FROM_PRICES: Sessions are inferred from price dates; ...
```

Provenance (`qr.Provenance`), price basis and availability (`qr.Declaration`) affect the declaration-related flags: their `trust()` methods inspect what you declare, without checking those claims against the data. Other flags reflect the supplied data and execution assumptions; for example, adding open prices removes the next-close proxy caveat, while the inferred-calendar caveat remains.

## Reference implementation parity

The engine and the Taiwan equity module were ported from a private research implementation. In the original porting comparison, on eight years of a Taiwan ETF (1,953 sessions, 16 cash dividends, one 4-for-1 split and a trading suspension), QuantRail matched the daily net asset value of five reference runs with **zero difference**: buy-and-hold, and three rules that sell (87 sells with securities transaction tax, including runs with a no-trade band and with doubled slippage). Units, cash, receivables, payables, commission, tax and slippage were also compared manually at that time; the automated parity test asserts daily NAV only. This comparison checks that the port reproduces the reference, not that the market model is correct.

That reference was itself checked independently: its buy-and-hold ledger was reconciled against a total-return index, with every difference explained by cash drag, costs and timing, and against a second data source. The data is not distributed; [`tests/test_reference_parity.py`](https://github.com/ting-hong-shieh/quantrail/blob/main/tests/test_reference_parity.py) reruns the daily NAV comparison when you point it at your own copy.

## Markets

| Module | Status | Covered | Not yet |
| --- | --- | --- | --- |
| `markets.tw_equity`: Taiwan equities and ETFs | Pre-alpha | T+2 settlement, commission with minimum fee, securities transaction tax as a sourced, effective-dated rule, cash dividends, splits, odd lots and board lots | Daily price limits, stock dividends ([#15](https://github.com/ting-hong-shieh/quantrail/issues/15)) |
| `markets.generic`: any market | Available | Proportional commission with minimum, sell tax | Market-specific rules |
| Crypto | Planned ([#5](https://github.com/ting-hong-shieh/quantrail/issues/5)) | | Spot, then perpetuals |

QuantRail **ships no market data**. You bring your own, or fetch it with your own credentials from sources whose terms allow it. There is no broker connectivity or live trading in this repository.

## Architecture

<p align="center">
  <img src="https://raw.githubusercontent.com/ting-hong-shieh/quantrail/main/assets/architecture.svg" width="900" alt="Animated flow: your data passes through data governance and the engine into a result with a trust report; accounting and market modules light up as they support the engine, research and stats light up as auxiliary tools for recording trials and analysing results; core types underlie everything">
</p>

Read the [architecture](https://github.com/ting-hong-shieh/quantrail/blob/main/docs/architecture.md) and the [decision records](https://github.com/ting-hong-shieh/quantrail/tree/main/docs/adr/) for the reasoning.

## Install

```bash
pip install quantrail
```

For development:

```bash
git clone https://github.com/ting-hong-shieh/quantrail.git
cd quantrail
uv sync
uv run pytest
```

## Contributing

Correctness comes before features: accounting and statistics changes need tests with independently computed expectations. Every commit is signed off (DCO). See [CONTRIBUTING.md](https://github.com/ting-hong-shieh/quantrail/blob/main/CONTRIBUTING.md).

## Licence

Apache-2.0. See [LICENSE](https://github.com/ting-hong-shieh/quantrail/blob/main/LICENSE) and [NOTICE](https://github.com/ting-hong-shieh/quantrail/blob/main/NOTICE). Data you use with QuantRail remains subject to its own source's terms.
