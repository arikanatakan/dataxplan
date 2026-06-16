# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/).

## [0.2.0] - 2026-06-17

### Added

- `parse` (and therefore `analyze`) now accepts the text, YAML and XML EXPLAIN
  formats in addition to JSON, auto-detected from the input. JSON, YAML and XML
  are exact; the text format is parsed best-effort. YAML needs PyYAML
  (`dataxplan[yaml]`); XML uses the standard library.

## [0.1.1] - 2026-06-17

### Added

- Each finding now carries a `reference` to the documented PostgreSQL behaviour
  it relies on (and Leis et al. 2015 for the estimation rules), surfaced in
  `to_dict()`.

### Documentation

- A Methodology section with the metric formulas (self time, estimation error,
  spill detection) and a per-finding source table in the README.

## [0.1.0] - 2026-06-17

First release.

### Added

- `parse`: PostgreSQL `EXPLAIN (FORMAT JSON)` output into a typed `Plan` /
  `PlanNode` tree, tolerant of plans without ANALYZE or BUFFERS.
- Metrics: self (exclusive) time, share of total, estimation error, disk spills
  and buffers per node, with roll-ups.
- `analyze` returns a `Report` with documented-heuristic findings (hot
  sequential scans, large row mis-estimates, disk spills, filter discards,
  nested-loop blow-ups, index-only heap fetches, lossy bitmaps, JIT overhead),
  a `summary`, a JSON-safe `to_dict`, and an assertion API for CI
  (`has_seq_scan_on`, `max_estimation_error`, `spilled_to_disk`, `ok`).
- `compare`: regression diff of two plans (timing, shape, estimates, findings).
- Optional `Context` of catalog metadata (table sizes, indexed columns, stale
  statistics) that sharpens the findings.
- `text_tree` (dependency-free) and `plan_tree_chart` (needs matplotlib,
  `dataxplan[viz]`).
- `run_explain`: optional helper that runs EXPLAIN on a DB-API connection you
  provide; dataxplan depends on no driver.
- No runtime dependencies; every result carries provenance.
