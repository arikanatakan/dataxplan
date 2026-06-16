"""The public-dataset example plans parse and raise the documented findings."""

import json
import pathlib

import pytest

import dataxplan

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"

CASES = {
    "job_imdb_misestimate.json": {"estimate_off", "nested_loop_blowup"},
    "nyc_taxi_sort_spill.json": {"disk_spill", "seq_scan_hot"},
    "tpch_lineitem_filter.json": {"seq_scan_hot", "filter_discard"},
    "bosch_production_hash_join.json": {"seq_scan_hot", "estimate_off", "filter_discard"},
}


@pytest.mark.parametrize("name, expected", CASES.items())
def test_example_findings(name, expected):
    plan = json.loads((EXAMPLES / name).read_text())
    report = dataxplan.analyze(plan)
    ids = {f.id for f in report.findings}
    assert expected <= ids, f"{name}: got {ids}"
    # every example should be JSON-serialisable and summarise without error
    json.dumps(report.to_dict(), default=str)
    assert report.summary()
