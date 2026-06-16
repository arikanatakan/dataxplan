# dataxplan

[![CI](https://github.com/arikanatakan/dataxplan/actions/workflows/ci.yml/badge.svg)](https://github.com/arikanatakan/dataxplan/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/dataxplan?v=1)](https://pypi.org/project/dataxplan/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Read PostgreSQL `EXPLAIN` plans from Python: parse the plan, compute the numbers
people misread (self time and estimation error), flag documented problems,
compare plans, and guard them in CI. **No database connection, nothing leaves
your machine, deterministic output.**

You give it the output of `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ...`; it does
the rest locally.

![dataxplan framework: an EXPLAIN JSON plan (and optional catalog context) flows through parse, metrics and findings into a Report you can summarise, assert on in CI, turn into JSON, compare against another plan, or render as a text tree or chart; no database connection and deterministic](assets/framework.png)

It turns a plan into a deterministic read (here a query whose join was estimated
at 5 rows but produced 500,000):

```text
dataxplan
  execution time   1,505.00 ms   (planning 0.30 ms)
  nodes 3, depth 1
  worst row estimate   100000x off
  top by self time:
    Index Scan on b      1,000.00 ms (66%)
    Nested Loop          450.00 ms (30%)
findings:
  [HIGH] Row estimate is far off  (Nested Loop)
      estimated 5 rows, actual 500,000 (100000x under-estimate)
      -> run ANALYZE; if the columns are correlated consider extended statistics
  [MEDIUM] Nested loop with many iterations  (Nested Loop)
      the inner side executed 500,000 times
      -> usually an under-estimate upstream; a hash or merge join may be cheaper
```

## Why

Reading a plan by hand is error-prone (self time is per-loop and inclusive of
children, so the slow node is rarely the obvious one). The good tools that do
this are web pastebins (your production plan leaves your machine) or commercial
SaaS. dataxplan is local, free, programmatic and embeddable: run it in a script,
a notebook, your CI, or later an MCP server, and keep the plan in your own
environment.

```bash
pip install dataxplan
```

No runtime dependencies. The chart is optional (`pip install "dataxplan[viz]"`).

## Quick start

```python
import dataxplan

report = dataxplan.analyze(explain_json)   # the EXPLAIN (FORMAT JSON) output
print(report.summary())                    # the summary shown above
```

### From the command line

```bash
dataxplan plan.json                       # summary
dataxplan plan.json --tree                # also the annotated plan tree
dataxplan plan.json --json                # the full report as JSON
dataxplan before.json --compare after.json
psql -XqAt -c "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) <query>" | dataxplan
```

### Guard a plan in CI

Pin a critical query's plan in your test suite, so a code or schema change that
makes it regress fails the build. Nothing else in Python does this.

```python
def test_orders_lookup_stays_fast():
    report = dataxplan.analyze(get_explain("SELECT * FROM orders WHERE customer_id = %s"))
    assert not report.has_seq_scan_on("orders")
    assert report.max_estimation_error < 100
    assert not report.spilled_to_disk
```

### Compare two plans (before / after an index)

```python
print(dataxplan.compare(before_json, after_json).summary())
# dataxplan compare - IMPROVED
#   execution time   905.00 ms -> 0.08 ms (-100%)
#   resolved         filter_discard, seq_scan_hot
```

### Sharper findings with catalog context (optional)

```python
from dataxplan import Context, TableInfo
ctx = Context(tables={"orders": TableInfo("orders", row_count=10_000_000,
                                          indexed_columns=("id",))})
dataxplan.analyze(explain_json, context=ctx)
```

### Fetch a plan from a connection you already have (optional)

```python
plan = dataxplan.run_explain(conn, "SELECT * FROM orders WHERE id = %s", params=(42,))
dataxplan.analyze(plan)
```

`run_explain` calls `cursor.execute` on a DB-API connection you pass (psycopg,
psycopg2, ...); dataxplan does not depend on any driver. With `analyze=True` it
runs the query, so use `analyze=False` for a plan-only estimate.

## What it covers

| Area | What you get |
| --- | --- |
| Parse | `parse` -> a typed `Plan` / `PlanNode` tree from EXPLAIN (FORMAT JSON) |
| Metrics | self (exclusive) time, % of total, estimation error, disk spills, buffers |
| Findings | hot sequential scans, large row mis-estimates, disk spills, filter discards, nested-loop blow-ups, index-only heap fetches, lossy bitmaps, JIT overhead |
| Report | `summary`, `to_dict`, and an assertion API (`has_seq_scan_on`, `max_estimation_error`, `spilled_to_disk`, `ok`) for CI |
| Compare | `compare` two plans for regression (timing, shape, estimates, findings) |
| Render | `text_tree` (annotated, dependency-free) and `plan_tree_chart` (needs matplotlib) |
| Context | optional catalog metadata (sizes, indexes, stale stats) that sharpens findings |
| CLI | `dataxplan plan.json` (or stdin): summary, `--tree`, `--json`, `--compare` |

## Examples

Four plans from public datasets and benchmarks, each showing a different problem,
are in [`examples/`](examples/): the IMDB / Join Order Benchmark (a row
mis-estimate), the NYC TLC taxi trips (a sort that spills to disk), TPC-H
`lineitem` (a hot scan discarding most rows), and the Bosch Production Line
Performance manufacturing data set (a hash join with a large mis-estimate). For
instance:

```bash
dataxplan examples/job_imdb_misestimate.json
```

## What is out of scope

dataxplan analyses the **plan you give it**. By default it does not connect to a
database, run your queries, or read your schema, so a finding is a **documented
heuristic, not a guarantee**, and the suggestions are based on the plan alone. It
does not rewrite SQL or invent a cost model. It targets PostgreSQL
`FORMAT JSON` output (MySQL may follow).

## How the headline metrics work

- **Self time.** Postgres reports `Actual Total Time` per loop and inclusive of
  children, so a node's total is `Actual Total Time x Actual Loops`, and its
  self time is that minus the children's totals. Self time is where the work
  really happens.
- **Estimation error.** `Plan Rows` against `Actual Rows` (per loop); a large
  ratio is the usual root cause of a bad plan.

## References and validation

The metric arithmetic is verified by hand against the semantics PostgreSQL
documents (see [`tests/`](tests/)), and the heuristics are grounded in primary
and academic sources, written in our own words:

- [PostgreSQL documentation: EXPLAIN](https://www.postgresql.org/docs/current/sql-explain.html)
- [PostgreSQL wiki: Using EXPLAIN](https://wiki.postgresql.org/wiki/Using_EXPLAIN)
- V. Leis, A. Gubichev, A. Mirchev, P. Boncz, A. Kemper, T. Neumann, "How Good
  Are Query Optimizers, Really?", Proceedings of the VLDB Endowment 9(3), 2015 -
  the study of cardinality mis-estimation behind the Join Order Benchmark, which
  the `estimate_off` finding detects (see the JOB example in
  [`examples/`](examples/)).

Plan analysis has no single numeric ground truth the way a closed-form formula
does, so the claim here is deliberately narrow: the parsing and arithmetic are
correct against the documented format, and each heuristic cites the behaviour it
relies on.

## License

MIT. Written and maintained by [Atakan Arikan](https://github.com/arikanatakan),
MSc Student at Tsinghua University and Politecnico di Milano.
