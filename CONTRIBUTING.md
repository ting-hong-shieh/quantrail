# Contributing to QuantRail

Thank you for helping. QuantRail values correctness over features: a smaller change with tests that prove the behaviour is better than a large one without.

## Ground rules

1. **No market data in the repository.** Tests use synthetic fixtures. Do not commit vendor or exchange data, even small samples.
2. **No credentials.** API keys, tokens and account identifiers never belong in code, tests or examples.
3. **Respect data source terms.** Adapters are accepted only for sources whose terms allow programmatic access; document those terms in the adapter.
4. **Tests prove behaviour.** Accounting and statistics changes need tests with independently computed expected values, not values produced by the code under test.
5. **Explain refusals.** When the code cannot support an action, it returns or raises a reason, never an invented value.

## Developer Certificate of Origin

Every commit must be signed off, certifying the [Developer Certificate of Origin](https://developercertificate.org/):

```bash
git commit -s -m "Describe the change"
```

## Development

```bash
uv sync
uv run ruff check .
uv run pytest
```

Pull requests run the same checks in CI. Keep pull requests focused on one change.

## Language

Code, issues, pull requests and the English documentation are in English. Traditional Chinese translations live under `docs/zh-TW/` and in `README.zh-TW.md`; the English text is the source of truth.
