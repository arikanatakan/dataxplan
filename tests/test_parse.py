import json

import pytest

import dataxplan


def test_parse_tree(load):
    plan = dataxplan.parse(load("misestimate_nestloop.json"))
    assert plan.root.node_type == "Nested Loop"
    assert len(plan.root.children) == 2
    assert plan.root.children[0].relation == "a"
    assert plan.execution_time == 1505.0
    assert plan.planning_time == 0.3
    assert plan.has_actuals


def test_parse_accepts_json_string(load):
    plan = dataxplan.parse(json.dumps(load("clean.json")))
    assert plan.root.node_type == "Index Scan"
    assert plan.root.label == "Index Scan on users"


def test_parse_no_analyze(load):
    plan = dataxplan.parse(load("no_analyze.json"))
    assert not plan.has_actuals
    assert plan.execution_time is None


def test_parse_bare_node():
    plan = dataxplan.parse({"Node Type": "Result", "Plan Rows": 1})
    assert plan.root.node_type == "Result"


def test_parse_rejects_non_plan():
    with pytest.raises(ValueError):
        dataxplan.parse({"random": "thing"})
    with pytest.raises(ValueError):
        dataxplan.parse([])


def test_paths_are_assigned(load):
    plan = dataxplan.parse(load("misestimate_nestloop.json"))
    assert plan.root.path == ()
    assert plan.root.children[0].path == (0,)
    assert plan.root.children[1].path == (1,)
