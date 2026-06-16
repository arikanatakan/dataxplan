import json

import pytest

import dataxplan


def test_regression(load):
    c = dataxplan.compare(load("clean.json"), load("seq_scan_filter.json"))
    assert c.verdict == "regressed"
    assert any("Seq Scan" in a for a in c.appeared)
    assert c.delta_ms > 0


def test_improvement(load):
    c = dataxplan.compare(load("seq_scan_filter.json"), load("clean.json"))
    assert c.verdict == "improved"


def test_same_plan_is_similar(load):
    c = dataxplan.compare(load("clean.json"), load("clean.json"))
    assert c.verdict == "similar"
    assert c.delta_ms == pytest.approx(0.0)


def test_compare_accepts_reports(load):
    a = dataxplan.analyze(load("clean.json"))
    b = dataxplan.analyze(load("sort_spill.json"))
    c = dataxplan.compare(a, b)
    assert c.verdict == "regressed"


def test_compare_to_dict_json_safe(load):
    c = dataxplan.compare(load("clean.json"), load("sort_spill.json"))
    json.dumps(c.to_dict())
    assert "compare" in c.summary()
