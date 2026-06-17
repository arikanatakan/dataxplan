import pytest

import dataxplan
from dataxplan.metrics import compute_metrics

# The same Seq Scan plan in three non-JSON formats.

TEXT_PLAN = """\
Seq Scan on orders  (cost=0.00..35811.00 rows=5 width=244) (actual time=0.030..900.000 rows=5 loops=1)
  Filter: (status = 'X'::text)
  Rows Removed by Filter: 10000000
  Buffers: shared hit=1000 read=120000
Planning Time: 0.400 ms
Execution Time: 905.000 ms
"""

YAML_PLAN = """\
- Plan:
    Node Type: "Seq Scan"
    Relation Name: "orders"
    Startup Cost: 0.00
    Total Cost: 35811.00
    Plan Rows: 5
    Plan Width: 244
    Actual Startup Time: 0.030
    Actual Total Time: 900.000
    Actual Rows: 5
    Actual Loops: 1
    Filter: "(status = 'X'::text)"
    Rows Removed by Filter: 10000000
  Planning Time: 0.400
  Execution Time: 905.000
"""

XML_PLAN = """\
<explain xmlns="http://www.postgresql.org/2009/explain">
  <Query>
    <Plan>
      <Node-Type>Seq Scan</Node-Type>
      <Relation-Name>orders</Relation-Name>
      <Startup-Cost>0.00</Startup-Cost>
      <Total-Cost>35811.00</Total-Cost>
      <Plan-Rows>5</Plan-Rows>
      <Plan-Width>244</Plan-Width>
      <Actual-Startup-Time>0.030</Actual-Startup-Time>
      <Actual-Total-Time>900.000</Actual-Total-Time>
      <Actual-Rows>5</Actual-Rows>
      <Actual-Loops>1</Actual-Loops>
      <Filter>(status = 'X'::text)</Filter>
      <Rows-Removed-by-Filter>10000000</Rows-Removed-by-Filter>
    </Plan>
    <Planning-Time>0.400</Planning-Time>
    <Execution-Time>905.000</Execution-Time>
  </Query>
</explain>
"""

# A nested plan in the text format, to exercise tree building from indentation.
NESTED_TEXT = """\
Nested Loop  (cost=0.50..9999.00 rows=5 width=40) (actual time=0.050..1500.000 rows=500000 loops=1)
  ->  Index Scan using a_pkey on a  (cost=0.00..100.00 rows=5 width=8) (actual time=0.020..50.000 rows=500000 loops=1)
  ->  Index Scan using b_idx on b  (cost=0.00..2.00 rows=1 width=8) (actual time=0.001..0.002 rows=1 loops=500000)
Planning Time: 0.300 ms
Execution Time: 1505.000 ms
"""


# A parallel plan in the text format: the worker scan must normalise to "Seq Scan".
PARALLEL_TEXT = """\
Gather  (cost=1000.00..50000.00 rows=4000000 width=120) (actual time=0.500..3000.000 rows=4000000 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  ->  Parallel Seq Scan on yellow_tripdata  (cost=0.00..40000.00 rows=1666667 width=120) (actual time=0.020..1500.000 rows=1333333 loops=3)
        Filter: (trip_distance > '50'::numeric)
        Rows Removed by Filter: 15000000
Planning Time: 0.300 ms
Execution Time: 3100.000 ms
"""


def _ids(report):
    return {f.id for f in report.findings}


def test_text_parses():
    plan = dataxplan.parse(TEXT_PLAN)
    assert plan.root.node_type == "Seq Scan"
    assert plan.root.relation == "orders"
    assert plan.execution_time == 905.0
    assert plan.has_actuals
    ids = _ids(dataxplan.analyze(TEXT_PLAN))
    assert "seq_scan_hot" in ids and "filter_discard" in ids


def test_xml_parses():
    plan = dataxplan.parse(XML_PLAN)
    assert plan.root.node_type == "Seq Scan"
    assert plan.root.relation == "orders"
    assert plan.execution_time == 905.0
    assert "seq_scan_hot" in _ids(dataxplan.analyze(XML_PLAN))


def test_yaml_parses():
    pytest.importorskip("yaml")
    plan = dataxplan.parse(YAML_PLAN)
    assert plan.root.node_type == "Seq Scan"
    assert plan.root.relation == "orders"
    assert plan.execution_time == 905.0
    assert "seq_scan_hot" in _ids(dataxplan.analyze(YAML_PLAN))


def test_text_tree_and_self_time():
    plan = dataxplan.parse(NESTED_TEXT)
    assert plan.root.node_type == "Nested Loop"
    assert len(plan.root.children) == 2
    assert plan.root.children[0].relation == "a"
    assert plan.root.children[0].index_name == "a_pkey"
    m = {x.label: x for x in compute_metrics(plan)}
    assert m["Nested Loop"].self_time == pytest.approx(450.0)   # 1500 - (50 + 1000)
    assert m["Index Scan on b"].self_time == pytest.approx(1000.0)
    ids = _ids(dataxplan.analyze(NESTED_TEXT))
    assert "estimate_off" in ids and "nested_loop_blowup" in ids


def test_parallel_text_is_normalised():
    report = dataxplan.analyze(PARALLEL_TEXT)
    # "Parallel Seq Scan" reads as "Seq Scan", as the JSON format reports it
    assert report.has_seq_scan_on("yellow_tripdata")
    assert "seq_scan_hot" in _ids(report)
    assert report.rollup["parallel"] is True
    assert "parallel" in report.summary().lower()


def test_formats_agree_with_json():
    baseline = [{"Plan": {
        "Node Type": "Seq Scan", "Relation Name": "orders",
        "Startup Cost": 0.0, "Total Cost": 35811.0, "Plan Rows": 5,
        "Plan Width": 244, "Actual Startup Time": 0.03,
        "Actual Total Time": 900.0, "Actual Rows": 5, "Actual Loops": 1,
        "Filter": "(status = 'X'::text)", "Rows Removed by Filter": 10000000},
        "Planning Time": 0.4, "Execution Time": 905.0}]
    json_ids = _ids(dataxplan.analyze(baseline))
    assert _ids(dataxplan.analyze(TEXT_PLAN)) == json_ids
    assert _ids(dataxplan.analyze(XML_PLAN)) == json_ids
