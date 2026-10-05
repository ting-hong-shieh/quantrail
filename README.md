# QuantRail

**Quantitative research you can trust.** QuantRail is a Python library for backtests whose results state, on their face, how far they can be trusted.

[繁體中文](README.zh-TW.md) · [Architecture](docs/architecture.md) · [Decisions](docs/adr/) · [Contributing](CONTRIBUTING.md)

> Status: early development (v0.x). APIs will change. Nothing here is investment advice.

## Why another backtesting library?

Most backtests are easy to make look good and hard to trust:

- positions are multiplied by adjusted returns, so dividends, splits and settlement are approximated or double-counted;
- nobody records which data version, licence or availability time a result depended on;
- the many variants tried before the "winner" are forgotten, so overfitting goes unmeasured.

QuantRail is built around three pillars:

| Pillar | What you get |
| --- | --- |
| **Data governance** | Versioned, hashed datasets with manifests: source, licence, price basis, point-in-time availability, quality checks. "Unknown" is allowed and reported, never hidden. |
| **Ledger-accurate simulation** | Raw prices plus explicit events (fees, taxes, dividends, splits, funding, settlement). Every day's change in wealth must reconcile. |
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

## Scope

- Markets: pluggable market modules. The Taiwan equity module handles T+2 settlement, cash dividends, splits, odd-lot and board-lot sizes and the securities transaction tax; daily price limits and stock dividends are not modelled yet. Crypto is next.
- QuantRail **ships no market data**. You bring your own, or fetch it with your own credentials from sources whose terms allow it.
- No broker connectivity or live trading in this repository.

## Install

Not yet published. For development:

```bash
git clone https://github.com/ting-hong-shieh/quantrail.git
cd quantrail
uv sync
uv run pytest
```

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Data you use with QuantRail remains subject to its own source's terms.
