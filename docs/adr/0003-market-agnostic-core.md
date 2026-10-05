# ADR 0003: Market-agnostic core with Decimal quantities and per-currency cash

- Status: accepted
- Date: 2026-10-05

## Context

The accounting code QuantRail grows from was Taiwan-shaped: integer quantities, a single cash balance without currency, and a closed list of Taiwan venues. Crypto needs fractional quantities, several currencies and funding payments; US equities need different calendars and fees.

## Decision

- Quantities are `Decimal`, validated against an instrument's quantity step and minimum.
- Cash is held per currency; converting between currencies is an explicit, recorded event.
- Venues, asset classes, cost models, settlement rules, order constraints and event types are supplied by market modules. The core contains no exchange-specific constant.
- A market module's behaviour is pinned by tests that reproduce reference results computed independently.

## Consequences

- Adding a market means adding a module and its reference tests, never forking the ledger or the engine.
- The first module (Taiwan equities) must reproduce an existing reference simulation exactly before it is considered done.
