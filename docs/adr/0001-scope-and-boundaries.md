# ADR 0001: Scope and repository boundaries

- Status: accepted
- Date: 2026-10-05

## Context

The author's existing work mixed three concerns in one private codebase: Taiwan market data and recording, a research platform, and accounting primitives. Research moved to a separate private repository; recording keeps running privately. The reusable parts deserve a clean, public home.

## Decision

QuantRail contains only what is safe and useful to publish: data governance, ledger-accurate simulation, market modules and research discipline. Credentials, deployments, market data, live recording and private studies stay outside.

A component is split into its own repository only when its deployment target, credentials or release cadence differ, not merely because it is a different feature or market.

## Consequences

- Market data never enters this repository; tests use synthetic fixtures.
- A future live-execution service would be a separate repository that depends on QuantRail's contracts.
- New markets are modules here, not new repositories.
