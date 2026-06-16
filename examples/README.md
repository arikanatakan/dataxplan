# Examples

Four example plans drawn from well-known public datasets and benchmarks, each
showing a different problem dataxplan flags. Run any of them:

```bash
dataxplan examples/job_imdb_misestimate.json
dataxplan examples/nyc_taxi_sort_spill.json --tree
dataxplan examples/tpch_lineitem_filter.json
dataxplan examples/bosch_production_hash_join.json
```

The datasets and their schemas are real and linked below; the plan structures are
realistic for the queries shown. The exact times are illustrative (your numbers
depend on data size, hardware and settings), so these demonstrate how dataxplan
reads a plan rather than benchmarking the datasets themselves.

## 1. IMDB / Join Order Benchmark - a row mis-estimate

**Dataset:** the IMDB data set used by the Join Order Benchmark, the standard
benchmark for cardinality estimation. Leis et al., *How Good Are Query
Optimizers, Really?* (VLDB 2015); schema and queries at
<https://github.com/gregrahn/join-order-benchmark>.

**Query (shape):** join `movie_keyword` to `title` filtering on a keyword.

dataxplan flags `estimate_off` (the optimizer expected 2 rows, the join produced
480,000, a 240,000x under-estimate) and `nested_loop_blowup` (the inner side ran
480,000 times). This is exactly what the benchmark was built to expose.

## 2. NYC TLC Yellow Taxi trips - a sort that spills to disk

**Dataset:** the New York City Taxi & Limousine Commission trip records, a
public multi-billion-row data set.
<https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page>

**Query (shape):** order long trips by fare over millions of rows.

dataxplan flags `disk_spill` (the sort used an external merge on disk) and
`seq_scan_hot` (the sequential scan of `yellow_tripdata` is a large share of the
time).

## 3. TPC-H lineitem - a hot scan discarding most rows

**Dataset:** TPC-H, the standard decision-support benchmark, scalable to
hundreds of gigabytes. <https://www.tpc.org/tpch/>

**Query (shape):** aggregate over `lineitem` with a selective predicate on
`l_quantity`.

dataxplan flags `seq_scan_hot` (the scan of `lineitem` is almost all of the
time) and `filter_discard` (it read 59 million rows and kept 2 million), which
points at a missing index for the predicate.

## 4. Bosch Production Line Performance - a manufacturing hash join

**Dataset:** the Bosch Production Line Performance data set, a large public
manufacturing data set (millions of parts with measurements across production
stations, to predict internal failures).
<https://www.kaggle.com/competitions/bosch-production-line-performance>

**Query (shape):** join part-level `measurements` to the failed `parts` and
count by station.

dataxplan flags `seq_scan_hot` (the 48-million-row scan of `measurements` is most
of the time), `estimate_off` (the join was estimated at 300 rows but produced
288,000, a 960x under-estimate) and `filter_discard` (the scan of `parts` kept
6,000 failed parts out of 1.2 million). It points at partitioning or indexing the
measurements table by part or station.
