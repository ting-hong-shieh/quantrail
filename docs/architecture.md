# QuantRail architecture

Status: draft v0.1 (2026-10-05). Decisions referenced here are recorded as ADRs in [`docs/adr/`](adr/). A Traditional Chinese translation lives in [`docs/zh-TW/architecture.md`](zh-TW/architecture.md); this English file is the source of truth.

## 1. What QuantRail is

QuantRail is a Python library for **data governance and ledger-accurate simulation**. It focuses on two things:

1. **Data governance.** Every dataset is a versioned, hashed snapshot with a manifest that records where it came from, under what terms, what kind of prices it contains and the declared availability rule. That rule is text; it does not filter records by availability time.
2. **Ledger-accurate simulation.** Wealth is computed by a ledger from raw prices and explicit events (fills, fees, taxes, dividends, splits, funding, settlement), not by multiplying positions by returns. The engine records a daily NAV identity residual without enforcing a tolerance.

The goal is that a result produced with QuantRail states, on its face, how far it can be trusted.

### Non-goals

- QuantRail **ships no market data** and no scrapers for sources whose terms forbid automated access.
- It is not a broker connector or a live-trading engine. Execution services may be built on its contracts later; credentials never belong in this repository.
- It does not promise profitable strategies. "No rule beat the baseline" is a valid, complete research result.

## 2. Principles

| Principle | Consequence |
| --- | --- |
| One source of accounting truth | Backtests and any future execution share the same ledger and cost contracts. Markets differ by module, not by forked engines. |
| Raw prices for wealth, adjusted series only for signals | Dividends and splits are events in the ledger. A total-return index may drive signals but never values a position. |
| Point in time | Availability is currently a dataset declaration; records are not filtered by availability time. The research workflow is responsible for restricting inputs to information available at decision time. |
| "Unknown" is a value, not an error | Provenance, licence, price basis and availability may be `unknown`. They are recorded and surface as warnings in a trust report; they do not block private research ([ADR 0002](adr/0002-unknown-provenance-is-a-value.md)). |
| Explicit versions only | Datasets are loaded by explicit version and verified by hash. There is no `latest`. |
| Market-agnostic core | Quantities are `Decimal` with an instrument-defined step; cash is held per currency. Nothing in the core assumes a particular exchange ([ADR 0003](adr/0003-market-agnostic-core.md)). |
| Fail closed, explain why | When the evidence does not support an action (no valid quote, unaffordable order, unknown rule), the result is a refusal with a reason code, never an invented value. |

## 3. Layers

```text
quantrail
├── core          Instruments, quantities, currencies, provenance, trust flags
├── data          Raw batches, manifests, curated datasets, ingest of user data
├── accounting    Multi-currency ledger, positions, settlement, corporate events
├── markets       Market modules: tw_equity (first), crypto (next)
├── engine        Daily simulation loop: decisions -> orders -> fills -> ledger
├── research      Trial registry (auxiliary tool)
├── stats         Metrics, paired block bootstrap, Holm, DSR, PBO
└── report        Trust report and result summaries
```

Dependencies point downwards only: `core` depends on nothing in QuantRail; `markets` depend on `core` and `accounting`; `engine` depends on everything above it; `research` and `stats` do not depend on any particular market.

## 4. Core concepts

| Concept | Meaning |
| --- | --- |
| `Instrument` | Stable identifier, venue, asset class, quote currency, quantity step and minimum, price tick. |
| `Quantity` | `Decimal`, validated against the instrument's step (1 share, 1000 shares, 0.00001 BTC). |
| `Money` | `Decimal` amount plus currency. Arithmetic across currencies requires an explicit conversion. |
| `Provenance` | Source, licence, terms URL, retrieval time; each field may be `unknown`. |
| `Declaration` | What a dataset claims about itself: price basis (raw / split-adjusted / total-return / unknown), availability rule, corporate actions present or not. |
| `TrustFlag` | A machine-readable caveat (`LICENCE_UNKNOWN`, `ACCOUNTING_APPROXIMATE`, `AVAILABILITY_UNVERIFIED`, ...) with severity and message. |
| `LedgerEvent` | Fill, fee, tax, cash dividend entitlement and payment, split, funding payment, settlement. |
| `MarketModule` | Supplies a market's calendar rules, cost model, settlement rule, order constraints and event types. |

## 5. Data governance

```text
fetch (adapter, user's own credentials)  ─┐
                                           ├─> raw batch: bytes as received + manifest (URL, time, SHA-256, provenance)
user files (CSV / Parquet / DataFrame)   ─┘
        │
        ▼
curate (deterministic, offline) ──> curated dataset version: tables + manifest (sources, declarations, checks, trust flags)
        │
        ▼
load by (dataset_id, version) ──> hash-verified tables + manifest + trust report
```

- Raw batches are append-only and never overwritten. A partial batch cannot be curated.
- Curation is offline and deterministic: the same raw batch and code give the same tables.
- `ingest()` is the entry point for data a user found elsewhere. Only a price table is required; everything else defaults to `unknown` and is reported.
- Adapters live in `quantrail.data.sources`. An adapter is accepted only for sources whose terms allow programmatic access; each adapter documents those terms and fills provenance automatically. Restricted vendors may be optional extras, documented as such.

### When provenance must be known

Private research never requires it. Exporting or sharing a dataset, publishing a report, and any commercial use do: those operations refuse, or require an explicit acknowledgement, when the licence is `unknown`.

## 6. Accounting and simulation

The engine runs one loop per session:

1. Apply events effective before the open (splits, dividend entitlements, funding).
2. Turn pending targets into orders; size them with the market's constraints and the cash actually available (receivables are not spendable).
3. Fill at the modelled price; book fees and taxes; schedule settlement.
4. Settle what is due; convert paid dividends into cash.
5. Value at the close (last valid price on untradable days, flagged) and record the residual of the identity

   `Δ NAV = overnight P&L + intraday P&L + entitlements − fees − taxes − slippage`.

Untradable sessions produce `NO_FILL` with a reason (`SUSPENDED`, `RAW_PRICE_MISSING`, `INVALID_QUOTE`, `INSUFFICIENT_CASH`, `LOT_CONSTRAINT`). Policies that are research choices (signal timing, no-trade bands, dividend reinvestment, terminal liquidation) are parameters of the study, not of the market module.

### Acceptance test for the first market module

The Taiwan equity module must reproduce, day by day, the private implementation it was ported from, on an ETF over eight years with sixteen dividends and one 4-for-1 split. That earlier implementation was itself checked independently: its buy-and-hold ledger was reconciled against a total-return index (every difference explained by cash drag, costs and timing) and against a second data source. Matching it proves the port is faithful; the independent evidence is that reconciliation. The data is not distributed.

## 7. Auxiliary research tools

Research design, rule freezing and out-of-sample policy belong to the user's own research workflow. QuantRail does not freeze experiment contracts or seal holdout data.

- **Trial registry.** Append-only JSONL. A trial is `REGISTERED` before it runs and gets exactly one terminal status (`COMPLETED`, `FAILED`, `BLOCKED`). Each records configuration hash, data manifest hash, code commit, dirty flag and a source fingerprint.
- **Statistics.** Paired circular block bootstrap with shared indices, Holm correction across challengers, deflated Sharpe ratio, CSCV probability of backtest overfitting, and BRAIN-style summary metrics. None of these is presented as a probability of future profit.

## 8. Public and private boundary

| Public (this repository) | Private (your environment) |
| --- | --- |
| Library code, market modules, adapters for permissively licensed sources | Credentials, schedules, deployment |
| Synthetic test fixtures | Market data (raw and curated) |
| Documentation and examples using openly licensed data | Strategies, studies and results you do not want to publish |

## 9. Roadmap

| Milestone | Content |
| --- | --- |
| M0 Foundation | Licence, contribution rules (DCO), CI, architecture and ADRs |
| M1 Core and data governance | `core` types, provenance and trust flags, datasets, `ingest()` |
| M2 Auxiliary research tools | Trial registry, metrics, inference |
| M3 Accounting and Taiwan equities | Multi-currency ledger, engine, `tw_equity` module, acceptance test |
| M4 Crypto | Spot first (fractional quantities, maker/taker fees, 24/7 calendar), then perpetuals (funding, margin) |
| M5 Examples | End-to-end tutorials on openly licensed data, in English and Traditional Chinese |
