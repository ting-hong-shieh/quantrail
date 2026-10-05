# Changelog

All notable changes to QuantRail are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/); before 1.0, a minor version may break the API.

## [Unreleased]

### Changed

- Position QuantRail around data governance and ledger-accurate simulation, with a new assumptions-focused tagline. Trial recording and statistical tools remain available as auxiliary tools; research design, rule freezing and out-of-sample policy belong to the user's workflow.
- Correct the English and Traditional Chinese README and architecture claims about frozen contracts, holdout sealing, NAV residual enforcement, declaration-based trust flags and availability filtering. Distinguish historical manual comparisons from automated daily NAV parity checks, and describe parity as evidence of a faithful port rather than market-model correctness.
- Align the Taiwan equity module's documented status with pre-alpha and regenerate the social preview and architecture diagram to match the revised wording. These changes update documentation, metadata and image text; simulation, research and statistics behaviour is unchanged.

## [0.1.1] - 2026-10-06

### Fixed

- The README on PyPI shows its images and links (they are now absolute URLs; a test keeps them so).
- Source snapshots in the trial registry are byte-for-byte deterministic (the gzip header no longer records the time).

### Changed

- CI and publishing use current major versions of their GitHub Actions (Node.js 24 runtimes; artifact downloads now fail on digest mismatch).
- The source distribution ships only what is needed to build and test the package (about 43 KB instead of about 450 KB); README images stay on GitHub.
- The README shows the PyPI version and installs with `pip install quantrail`.

## [0.1.0] - 2026-10-06

First pre-release.

### Added

- **Core types** (`quantrail.core`): `Provenance` and `Declaration` where `unknown` is an allowed, flagged value; `TrustFlag` and `TrustReport`; `Money` with `Decimal` amounts per currency; `Instrument` with quantity steps (shares, board lots, fractional crypto).
- **Data governance** (`quantrail.datasets`): versioned, hash-verified datasets loaded by explicit version only; `ingest()` for user tables (only a date and a close are required); `export_dataset()` refuses an unknown licence unless acknowledged.
- **Research discipline**: append-only trial registry with code fingerprints (`quantrail.research.trials`); metrics with fixed formulas and a BRAIN-style summary (`quantrail.stats.metrics`); paired circular block bootstrap, Holm correction, deflated Sharpe ratio and CSCV PBO (`quantrail.stats.inference`).
- **Accounting and simulation**: multi-currency ledger with settlement-dated cash (`quantrail.accounting.ledger`); next-open target-weight engine with `NO_FILL` reasons, no-trade band, buy-only dividend reinvestment and a daily NAV identity (`quantrail.engine`).
- **Markets**: Taiwan equities and ETFs (`quantrail.markets.tw_equity`) with T+2, commission with minimum fee and a sourced, effective-dated securities transaction tax rule; a generic proportional cost model (`quantrail.markets.generic`).
- **One-call API**: `quantrail.backtest()` on ingested data, with data-driven caveats merged into the trust report; refuses total-return prices combined with dividend events.
- **Verification**: the engine reproduces its private reference implementation to the cent (five runs, 1,953 sessions); `tests/test_reference_parity.py` reruns the comparison when pointed at your own copy of the data.
- **Documentation**: architecture (English and Traditional Chinese), ADRs 0001–0005, README quickstart executed by tests, generated logo, hero, animated architecture diagram and social preview.

### Known limitations

- Daily price limits and stock dividends are not modelled ([#15](https://github.com/ting-hong-shieh/quantrail/issues/15)).
- `backtest()` handles one instrument and infers sessions from price dates ([#16](https://github.com/ting-hong-shieh/quantrail/issues/16)).
- The ledger does not yet track average cost or realised P&L.
- Dependencies pin `pandas<3` ([#7](https://github.com/ting-hong-shieh/quantrail/issues/7)).
- Not yet published on PyPI.

[Unreleased]: https://github.com/ting-hong-shieh/quantrail/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/ting-hong-shieh/quantrail/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ting-hong-shieh/quantrail/releases/tag/v0.1.0
