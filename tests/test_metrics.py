"""The metric arithmetic is the core value, so it is hand-verified here.

For the nested-loop fixture: the loop's Actual Total Time is 1500 ms (1 loop);
the outer Index Scan is 50 ms (1 loop); the inner Index Scan is 0.002 ms per loop
over 500000 loops = 1000 ms. So the loop's self time is 1500 - (50 + 1000) = 450.
"""

import pytest

import dataxplan
from dataxplan.metrics import compute_metrics


def _by_label(plan):
    return {m.label: m for m in compute_metrics(plan)}


def test_self_time_de_loops_and_subtracts_children(load):
    m = _by_label(dataxplan.parse(load("misestimate_nestloop.json")))
    assert m["Nested Loop"].inclusive_time == pytest.approx(1500.0)
    assert m["Index Scan on b"].inclusive_time == pytest.approx(1000.0)  # 0.002*500000
    assert m["Index Scan on a"].self_time == pytest.approx(50.0)
    assert m["Index Scan on b"].self_time == pytest.approx(1000.0)
    assert m["Nested Loop"].self_time == pytest.approx(450.0)


def test_self_times_sum_to_root_inclusive(load):
    metrics = compute_metrics(dataxplan.parse(load("misestimate_nestloop.json")))
    assert sum(x.self_time for x in metrics) == pytest.approx(1500.0)


def test_estimation_error(load):
    m = _by_label(dataxplan.parse(load("misestimate_nestloop.json")))
    assert m["Nested Loop"].estimation_error == pytest.approx(100000.0)  # 500000/5
    assert m["Nested Loop"].estimation_factor == pytest.approx(100000.0)


def test_spill_detected(load):
    m = _by_label(dataxplan.parse(load("sort_spill.json")))
    assert m["Sort"].spilled is True
    assert m["Seq Scan on t"].spilled is False


def test_no_actuals_gives_none(load):
    metrics = compute_metrics(dataxplan.parse(load("no_analyze.json")))
    assert metrics[0].self_time is None
    assert metrics[0].estimation_error is None
