import pytest

import dataxplan


def test_text_tree(load):
    text = dataxplan.text_tree(dataxplan.analyze(load("misestimate_nestloop.json")))
    assert "Nested Loop" in text
    assert "Index Scan on a" in text
    assert "off]" in text          # the misestimate flag


def test_text_tree_marks_spill(load):
    text = dataxplan.text_tree(dataxplan.analyze(load("sort_spill.json")))
    assert "[spill]" in text


def test_plan_tree_chart_returns_figure(load):
    pytest.importorskip("matplotlib")
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    fig = dataxplan.plan_tree_chart(dataxplan.analyze(load("sort_spill.json")))
    assert isinstance(fig, Figure)
