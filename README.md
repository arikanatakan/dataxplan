# dataxplan

[![CI](https://github.com/arikanatakan/dataxplan/actions/workflows/ci.yml/badge.svg)](https://github.com/arikanatakan/dataxplan/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/dataxplan?v=2)](https://pypi.org/project/dataxplan/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Read PostgreSQL `EXPLAIN` plans from Python: parse the plan, compute the numbers
people misread (self time and estimation error), flag documented problems,
compare plans, and guard them in CI. **No database connection, nothing leaves
your machine, deterministic output.**

You give it the output of `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ...`; it does
the rest locally.

![dataxplan framework: an EXPLAIN JSON plan (and optional catalog context) flows through parse, metrics and findings into a Report you can summarise, assert on in CI, turn into JSON, compare against another plan, or render as a text tree or chart; no database connection and deterministic](assets/framework.png)

It turns a plan into a deterministic read. Here the Bosch manufacturing example
(`examples/`): a hash join over a 48-million-row scan of the production-line
measurements, estimated at 300 rows but producing 288,000 ([Bosch Production Line
Performance](https://www.kaggle.com/competitions/bosch-production-line-performance)):

```text
dataxplan
  execution time   2,601.00 ms   (planning 0.50 ms)
  nodes 5, depth 3
  worst row estimate   960x off
  spilled to disk      no
  top by self time:
    Seq Scan on measurements         2,200.00 ms (85%)
    Hash Join                        320.00 ms (12%)
    Seq Scan on parts                55.00 ms (2%)
    Aggregate                        20.00 ms (1%)
    Hash                             5.00 ms (0%)
findings:
  [HIGH] Hot sequential scan  (Seq Scan on measurements)
      sequential scan is 85% of execution time, reading 48,000,000 rows
      -> consider an index supporting the filter or join on measurements
  [HIGH] Row estimate is far off  (Hash Join)
      estimated 300 rows, actual 288,000 (960x under-estimate)
      -> run ANALYZE on the table; if the columns are correlated consider extended statistics
  [MEDIUM] Filter discards most rows read  (Seq Scan on parts)
      removed 1,194,000 rows by filter but kept only 6,000
      -> the predicate is not selective via the current access path; an index may help
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

Seven plans from public datasets and benchmarks (in [`examples/`](examples/)),
ordered here from the largest data set to the smallest. Each chart shows self
time per node, with the high-severity findings in a warning colour. The benchmark
and NYC sets are large in their own right; the semiconductor, automotive and
textile sets are smaller research samples of domains that run at production
scale, so those plans model a production-size query. Sizes and times are
illustrative.

### NYC TLC Yellow Taxi - a sort that spills to disk

The [NYC TLC trip records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
are a public, multi-billion-row data set. Ordering long trips by fare, dataxplan
flags `disk_spill` (an external-merge sort) over a hot sequential scan
(`seq_scan_hot`).

![dataxplan self-time chart for the NYC taxi example](assets/example_nyc.png)

### TPC-H lineitem - a hot scan discarding most rows

[TPC-H](https://www.tpc.org/tpch/) is the standard decision-support benchmark,
scalable to hundreds of gigabytes. A selective predicate on `l_quantity` flags
`seq_scan_hot` and `filter_discard` (59 million rows read, 2 million kept).

![dataxplan self-time chart for the TPC-H example](assets/example_tpch.png)

### IMDB / Join Order Benchmark - a row mis-estimate

The [Join Order Benchmark](https://github.com/gregrahn/join-order-benchmark)
(Leis et al., VLDB 2015) is the standard cardinality-estimation benchmark.
dataxplan flags `estimate_off` (2 rows estimated, 480,000 actual) and
`nested_loop_blowup`.

![dataxplan self-time chart for the Join Order Benchmark example](assets/example_job.png)

### Bosch Production Line Performance (manufacturing) - a hash join mis-estimate

The [Bosch Production Line Performance](https://www.kaggle.com/competitions/bosch-production-line-performance)
set is large public manufacturing data. dataxplan flags a hot 48-million-row scan
(`seq_scan_hot`), a 960x join mis-estimate (`estimate_off`) and a filter
discarding most rows (`filter_discard`).

![dataxplan self-time chart for the Bosch example](assets/example_bosch.png)

### SECOM (semiconductor) - an index-only scan hitting the heap

[SECOM](https://archive.ics.uci.edu/dataset/179/secom) (UCI) is sensor data from
a semiconductor line. dataxplan flags `index_only_heap_fetches` (9 million heap
fetches, so the table needs a VACUUM) and `estimate_off`.

![dataxplan self-time chart for the SECOM example](assets/example_secom.png)

### Mercedes-Benz manufacturing (automotive) - a lossy bitmap scan

The [Mercedes-Benz Greener Manufacturing](https://www.kaggle.com/competitions/mercedes-benz-greener-manufacturing)
set (Kaggle) is automotive test-bench data. dataxplan flags `lossy_bitmap` (6
million rows rechecked, so work_mem is too small) and `estimate_off`.

![dataxplan self-time chart for the Mercedes-Benz example](assets/example_mercedes.png)

### Garment factory (textile) - a hot scan discarding most rows

The [Productivity Prediction of Garment Employees](https://archive.ics.uci.edu/dataset/597/productivity+prediction+of+garment+employees)
set (UCI) is garment (textile) manufacturing data. dataxplan flags `seq_scan_hot`
and `filter_discard` on the production log.

![dataxplan self-time chart for the garment factory example](assets/example_garments.png)

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
