"""Derived metrics for a parsed plan.

The two numbers people most often get wrong when reading a plan are computed
here: the *self* (exclusive) time of a node, and the *estimation error*.

* Postgres reports ``Actual Total Time`` per loop and inclusive of children, so a
  node's total time is ``Actual Total Time x Actual Loops`` and its self time is
  that minus the total time of its children. Self time shows where the work
  actually happens.
* ``Plan Rows`` (estimated) against ``Actual Rows`` gives the estimation error,
  the usual root cause of a bad plan.
"""

from __future__ import annotations

from dataclasses import dataclass

from .parse import Plan


@dataclass(frozen=True)
class NodeMetrics:
    path: tuple[int, ...]
    label: str
    node_type: str
    relation: str | None
    loops: float
    inclusive_time: float | None
    self_time: float | None
    pct_self: float | None
    plan_rows: float
    actual_rows: float | None
    estimation_factor: float | None   # actual / estimated, per loop (>1 under-estimate)
    estimation_error: float | None    # how many times off, max(factor, 1/factor)
    spilled: bool
    shared_read: float
    rows_removed_by_filter: float | None
    heap_fetches: float | None

    def to_dict(self) -> dict:
        return {
            "path": list(self.path), "label": self.label,
            "node_type": self.node_type, "relation": self.relation,
            "loops": self.loops, "inclusive_time_ms": self.inclusive_time,
            "self_time_ms": self.self_time, "pct_self": self.pct_self,
            "plan_rows": self.plan_rows, "actual_rows": self.actual_rows,
            "estimation_factor": self.estimation_factor,
            "estimation_error": self.estimation_error, "spilled": self.spilled,
            "shared_read_blocks": self.shared_read,
            "rows_removed_by_filter": self.rows_removed_by_filter,
            "heap_fetches": self.heap_fetches,
        }


def compute_metrics(plan: Plan) -> list[NodeMetrics]:
    denom = plan.execution_time or plan.root.inclusive_time
    out: list[NodeMetrics] = []
    for node in plan.root.walk():
        incl = node.inclusive_time
        if incl is not None:
            kids = sum(c.inclusive_time or 0.0 for c in node.children)
            self_t = max(0.0, incl - kids)
        else:
            self_t = None
        # Clamped: under parallelism a node's de-looped time (total work across
        # workers) can exceed the wall-clock execution time.
        pct = min(1.0, self_t / denom) if (self_t is not None and denom) else None

        actual = node.actual_rows
        if actual is not None:
            est = max(node.plan_rows, 1.0)
            act = max(actual, 1.0)
            factor = act / est
            error = max(factor, 1.0 / factor)
        else:
            factor = error = None

        out.append(NodeMetrics(
            path=node.path, label=node.label, node_type=node.node_type,
            relation=node.relation, loops=node.actual_loops, inclusive_time=incl,
            self_time=self_t, pct_self=pct, plan_rows=node.plan_rows,
            actual_rows=actual, estimation_factor=factor, estimation_error=error,
            spilled=node.spilled_to_disk, shared_read=node.shared_read,
            rows_removed_by_filter=node.rows_removed_by_filter,
            heap_fetches=node.heap_fetches))
    return out


def _is_parallel(node) -> bool:
    return (node.raw.get("Parallel Aware") in (True, "true")
            or node.node_type in ("Gather", "Gather Merge"))


def rollups(plan: Plan, metrics: list[NodeMetrics]) -> dict:
    timed = [m for m in metrics if m.self_time is not None]
    top = sorted(timed, key=lambda m: m.self_time or 0.0, reverse=True)[:5]
    errors = [m.estimation_error for m in metrics if m.estimation_error is not None]
    return {
        "execution_time_ms": plan.execution_time,
        "planning_time_ms": plan.planning_time,
        "has_actuals": plan.has_actuals,
        "node_count": len(metrics),
        "max_depth": max((len(m.path) for m in metrics), default=0),
        "max_estimation_error": max(errors) if errors else None,
        "spilled_to_disk": any(m.spilled for m in metrics),
        "parallel": any(_is_parallel(n) for n in plan.root.walk()),
        "total_shared_read_blocks": sum(m.shared_read for m in metrics),
        "top_self_time": [
            {"label": m.label, "self_time_ms": m.self_time, "pct_self": m.pct_self}
            for m in top
        ],
    }
