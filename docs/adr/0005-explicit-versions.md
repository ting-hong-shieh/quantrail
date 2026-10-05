# ADR 0005: Explicit versions only

- Status: accepted
- Date: 2026-10-05

## Context

"Load the latest dataset" makes a result depend on when it was run. Two people, or the same person a week apart, silently get different answers.

## Decision

Datasets, experiment contracts and trial results are always addressed by an explicit identifier and version, and are verified by hash when loaded. There is no `latest` alias in the library API.

## Consequences

- Re-running a trial reproduces its inputs exactly or fails loudly.
- Helper commands may list available versions, but never choose one implicitly.
