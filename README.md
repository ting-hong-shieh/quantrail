<p align="center">
  <img src="assets/brand/option-b-verified.svg" width="96" alt="QuantRail logo">
</p>

<h1 align="center">QuantRail</h1>

<p align="center"><b>Backtests that tell you how far to trust them.</b><br>
Data governance · ledger-accurate simulation · research discipline</p>

<p align="center">
  <a href="https://github.com/ting-hong-shieh/quantrail/actions/workflows/ci.yml"><img src="https://github.com/ting-hong-shieh/quantrail/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white" alt="Python 3.11 | 3.12 | 3.13">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-0F766E" alt="Apache-2.0"></a>
  <img src="https://img.shields.io/badge/status-pre--alpha-F59E0B" alt="Status: pre-alpha">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

<p align="center">
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/adr/">Decisions</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <img src="assets/trust-report.svg" width="820" alt="A QuantRail result opens with a trust report listing everything it could not verify">
</p>

> **Status:** early development (v0.x); APIs will change. Nothing here is investment advice.

## Why QuantRail?

Most backtests are easy to make look good and hard to trust:

- positions are multiplied by adjusted returns, so dividends, splits and settlement are approximated or double-counted;
- nobody records which data version, licence or availability time a result depended on;
- the many variants tried before the "winner" are forgotten, so overfitting goes unmeasured.

QuantRail is built around three pillars:

| Pillar | What you get |
| --- | --- |
| **Data governance** | Versioned, hashed datasets with manifests: source, licence, price basis, point-in-time availability, quality checks. "Unknown" is allowed and reported, never hidden. |
| **Ledger-accurate simulation** | Raw prices plus explicit events (fees, taxes, dividends, splits, settlement). Every day's change in wealth must reconcile. |
| **Research discipline** | Append-only trial registry, frozen experiment contracts, sealed holdout data, and built-in paired block bootstrap, Holm correction, deflated Sharpe ratio and probability of backtest overfitting. |

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

The report starts with what QuantRail could not verify, because nothing was declared:

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

Declare provenance (`qr.Provenance`), price basis and availability (`qr.Declaration`), add open prices and corporate actions, and the caveats disappear one by one.

## Verified to the cent

The engine and the Taiwan equity module were ported from a private research implementation and must reproduce it exactly. On eight years of a Taiwan ETF (1,953 sessions, 16 cash dividends, one 4-for-1 split and a trading suspension), QuantRail matches the daily net asset value of five reference runs with **zero difference**: buy-and-hold, and three rules that sell (87 sells with securities transaction tax, including runs with a no-trade band and with doubled slippage). Units, cash, receivables, payables, commission, tax and slippage all match.

That reference was itself checked independently: its buy-and-hold ledger was reconciled against a total-return index, with every difference explained by cash drag, costs and timing, and against a second data source. The data is not distributed; [`tests/test_reference_parity.py`](tests/test_reference_parity.py) reruns the comparison when you point it at your own copy.

## Markets

| Module | Status | Covered | Not yet |
| --- | --- | --- | --- |
| `markets.tw_equity`: Taiwan equities and ETFs | Beta | T+2 settlement, commission with minimum fee, securities transaction tax as a sourced, effective-dated rule, cash dividends, splits, odd lots and board lots | Daily price limits, stock dividends ([#15](https://github.com/ting-hong-shieh/quantrail/issues/15)) |
| `markets.generic`: any market | Available | Proportional commission with minimum, sell tax | Market-specific rules |
| Crypto | Planned ([#5](https://github.com/ting-hong-shieh/quantrail/issues/5)) | | Spot, then perpetuals |

QuantRail **ships no market data**. You bring your own, or fetch it with your own credentials from sources whose terms allow it. There is no broker connectivity or live trading in this repository.

## Architecture

<p align="center">
  <img src="assets/architecture.svg" width="900" alt="Your data flows through data governance and the engine into a result with a trust report; accounting and market modules sit under the engine, research and stats judge the result, and core types are shared by every layer">
</p>

Read the [architecture](docs/architecture.md) and the [decision records](docs/adr/) for the reasoning.

## Install

Not yet on PyPI. For development:

```bash
git clone https://github.com/ting-hong-shieh/quantrail.git
cd quantrail
uv sync
uv run pytest
```

## Contributing

Correctness comes before features: accounting and statistics changes need tests with independently computed expectations. Every commit is signed off (DCO). See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Data you use with QuantRail remains subject to its own source's terms.
