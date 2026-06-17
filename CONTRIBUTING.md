# Contributing

Thanks for your interest in dataxplan.

## Development setup

```
git clone https://github.com/arikanatakan/dataxplan
cd dataxplan
python -m pip install -e ".[dev]"
```

## Before opening a pull request

```
ruff check .
mypy dataxplan
pytest
```

All three must pass. A new finding should come with a fixture under
`tests/fixtures/` (a small EXPLAIN plan that triggers it) and a documented
source: the PostgreSQL behaviour it relies on, in your own words, cited in the
finding's `reference` field.

## Scope

dataxplan reads the plan you give it, locally and deterministically. It does not
connect to a database by default, rewrite SQL, or invent a cost model; a finding
is a documented heuristic, not a guarantee. New findings and formats are welcome
when they are grounded in documented behaviour and tested against a fixture.

## Conventions

- Keep the `Report` and result contract append-only: add fields, do not rename or
  remove.
- Compute from the fields PostgreSQL documents for `EXPLAIN (ANALYZE, BUFFERS,
  FORMAT JSON)`; ground each finding in a documented source.
