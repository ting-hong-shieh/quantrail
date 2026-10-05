# ADR 0002: "Unknown" provenance is a value, not an error

- Status: accepted
- Date: 2026-10-05

## Context

Users often cannot say where a CSV came from, which licence applies, whether prices are adjusted, or when a value became available. Refusing such data would exclude most users; silently accepting it would overstate how trustworthy their results are.

## Decision

Provenance (source, licence, terms URL, retrieval time) and declarations (price basis, availability rule, presence of corporate actions) accept the value `unknown`, which is also the default. Every `unknown` produces a `TrustFlag` that travels with the dataset into every result and appears at the top of reports.

Only operations that affect other people require a known licence: exporting or sharing a dataset, publishing a report, and commercial use. Those refuse, or require an explicit acknowledgement, when the licence is unknown.

Built-in adapters fill provenance automatically.

## Consequences

- The minimum input for a backtest is a price table.
- Results always state their caveats, for example "licence unknown", "accounting approximate: no corporate actions", "availability unverified".
