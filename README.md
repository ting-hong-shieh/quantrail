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

## Scope

- Markets: Taiwan equities first, crypto next, via pluggable market modules.
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
