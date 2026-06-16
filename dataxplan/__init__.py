"""dataxplan - read PostgreSQL EXPLAIN plans, locally and deterministically.

Give it the output of ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ...`` and it
parses the plan, computes the metrics people misread (self time, estimation
error, disk spills), and flags documented problems. No database connection is
required and nothing leaves your machine.

    import dataxplan

    report = dataxplan.analyze(explain_json)
    print(report.summary())

    # guard a plan in a test (fail CI if it regresses)
    assert not report.has_seq_scan_on("orders")
    assert report.max_estimation_error < 100
    assert not report.spilled_to_disk

    # compare two plans (before/after an index)
    print(dataxplan.compare(before_json, after_json).summary())

The findings are documented heuristics, not guarantees, and the analysis is of
the plan you provide; it does not run your queries or read your schema unless you
choose to supply catalog context.
"""

from ._result import Finding
from ._version import __version__
from .compare import Comparison, compare
from .context import Context, TableInfo
from .metrics import NodeMetrics
from .parse import Plan, PlanNode, parse
from .render import plan_tree_chart, text_tree
from .report import Report, analyze
from .run import run_explain

__all__ = [
    # core flow
    "parse", "analyze", "compare",
    # types
    "Plan", "PlanNode", "Report", "NodeMetrics", "Finding", "Comparison",
    "Context", "TableInfo",
    # render and helpers
    "text_tree", "plan_tree_chart", "run_explain",
    "__version__",
]
