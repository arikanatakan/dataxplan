import json

import pytest

import dataxplan


def test_assertion_api(load):
    r = dataxplan.analyze(load("seq_scan_filter.json"))
    assert r.has_seq_scan_on("orders")
    assert not r.has_seq_scan_on("nope")
    assert not r.spilled_to_disk
    assert not r.ok                       # a high-severity finding was raised
    assert r.execution_time_ms == 905.0


def test_max_estimation_error(load):
    r = dataxplan.analyze(load("misestimate_nestloop.json"))
    assert r.max_estimation_error == pytest.approx(100000.0)


def test_spill_flag(load):
    assert dataxplan.analyze(load("sort_spill.json")).spilled_to_disk


def test_clean_plan_is_ok(load):
    r = dataxplan.analyze(load("clean.json"))
    assert r.ok
    assert r.max_estimation_error == pytest.approx(1.0)


def test_summary_and_to_dict_json_safe(load):
    r = dataxplan.analyze(load("seq_scan_filter.json"))
    assert "execution time" in r.summary()
    d = r.to_dict()
    json.dumps(d)
    assert d["meta"]["library"] == "dataxplan"


def test_no_analyze_report(load):
    r = dataxplan.analyze(load("no_analyze.json"))
    assert r.execution_time_ms is None
    assert "plan only" in r.summary()


def test_has_node(load):
    r = dataxplan.analyze(load("misestimate_nestloop.json"))
    assert r.has_node("Index Scan", "a")
    assert not r.has_node("Hash Join")
