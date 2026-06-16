# Examples

Seven example plans drawn from public datasets and benchmarks, across
manufacturing (automotive, textile, semiconductor) and general workloads, each
showing a different problem dataxplan flags. Run any of them:

```bash
dataxplan examples/bosch_production_hash_join.json
dataxplan examples/job_imdb_misestimate.json
dataxplan examples/nyc_taxi_sort_spill.json --tree
dataxplan examples/tpch_lineitem_filter.json
dataxplan examples/secom_semiconductor_index_only.json
dataxplan examples/mercedes_automotive_lossy_bitmap.json
dataxplan examples/garments_textile_seq_scan.json
```

The datasets and their schemas are real and linked below. Some (the Join Order
Benchmark, NYC taxi, TPC-H, Bosch) are large in their own right; the
semiconductor, automotive and textile sets are smaller research samples of
domains that run at production scale, so those plans model a production-size
query in the domain. In every case the plan structure is realistic and the exact
sizes and times are illustrative (your numbers depend on data, hardware and
settings); they show how dataxplan reads a plan rather than benchmarking the
datasets.

## 1. Bosch Production Line Performance - a manufacturing hash join

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

## 2. IMDB / Join Order Benchmark - a row mis-estimate

**Dataset:** the IMDB data set used by the Join Order Benchmark, the standard
benchmark for cardinality estimation. Leis et al., *How Good Are Query
Optimizers, Really?* (VLDB 2015); schema and queries at
<https://github.com/gregrahn/join-order-benchmark>.

**Query (shape):** join `movie_keyword` to `title` filtering on a keyword.

dataxplan flags `estimate_off` (the optimizer expected 2 rows, the join produced
480,000, a 240,000x under-estimate) and `nested_loop_blowup` (the inner side ran
480,000 times). This is exactly what the benchmark was built to expose.

## 3. NYC TLC Yellow Taxi trips - a sort that spills to disk

**Dataset:** the New York City Taxi & Limousine Commission trip records, a
public multi-billion-row data set.
<https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page>

**Query (shape):** order long trips by fare over millions of rows.

dataxplan flags `disk_spill` (the sort used an external merge on disk) and
`seq_scan_hot` (the sequential scan of `yellow_tripdata` is a large share of the
time).

## 4. TPC-H lineitem - a hot scan discarding most rows

**Dataset:** TPC-H, the standard decision-support benchmark, scalable to
hundreds of gigabytes. <https://www.tpc.org/tpch/>

**Query (shape):** aggregate over `lineitem` with a selective predicate on
`l_quantity`.

dataxplan flags `seq_scan_hot` (the scan of `lineitem` is almost all of the
time) and `filter_discard` (it read 59 million rows and kept 2 million), which
points at a missing index for the predicate.

## 5. SECOM semiconductor - an index-only scan that hits the heap

**Dataset:** SECOM, sensor and process-measurement data from a semiconductor
manufacturing line, on the UCI Machine Learning Repository.
<https://archive.ics.uci.edu/dataset/179/secom>

**Query (shape):** aggregate the measurements for one sensor over a fab's
`process_measurements` table.

dataxplan flags `index_only_heap_fetches` (the index-only scan still made 9
million heap fetches, so the visibility map is not set and the table needs a
VACUUM) and `estimate_off` (the scan was estimated at 90,000 rows but returned 9
million, 100x off).

## 6. Mercedes-Benz manufacturing - a lossy bitmap scan

**Dataset:** the Mercedes-Benz Greener Manufacturing data set (test-bench times
for permutations of car features), on Kaggle.
<https://www.kaggle.com/competitions/mercedes-benz-greener-manufacturing>

**Query (shape):** scan a plant's `test_runs` for one station.

dataxplan flags `lossy_bitmap` (the bitmap heap scan went lossy and rechecked 6
million rows, so work_mem is too small for the bitmap) and `estimate_off` (50,000
rows estimated, 8 million returned).

## 7. Garment factory (textile) - a hot scan discarding most rows

**Dataset:** the Productivity Prediction of Garment Employees data set, garment
(textile) manufacturing production data, on the UCI Machine Learning Repository.
<https://archive.ics.uci.edu/dataset/597/productivity+prediction+of+garment+employees>

**Query (shape):** group a factory's `production_log` by team, filtering on the
sewing department.

dataxplan flags `seq_scan_hot` (the scan of `production_log` is most of the time)
and `filter_discard` (it read 12 million rows and kept 500,000), which points at
an index on the department column.
