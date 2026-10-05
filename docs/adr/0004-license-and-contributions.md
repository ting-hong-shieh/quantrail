# ADR 0004: Apache-2.0 licence and Developer Certificate of Origin

- Status: accepted
- Date: 2026-10-05

## Context

The project aims for wide adoption while keeping the option to build commercial services around it.

## Decision

- Code is licensed under Apache-2.0, which is permissive and includes a patent grant.
- Contributions require a Developer Certificate of Origin sign-off (`git commit -s`), recorded on every commit.
- Commercial offerings, if any, live outside this repository (hosted services, premium data adapters, support); the core stays Apache-2.0.

## Consequences

- Anyone may use QuantRail commercially, including competitors.
- Data accessed through QuantRail is governed by its own source terms, stated in `NOTICE` and in each adapter.
