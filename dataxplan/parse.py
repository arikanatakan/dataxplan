"""Parse PostgreSQL ``EXPLAIN (FORMAT JSON)`` output into a typed plan tree.

The input is whatever ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ...`` returns: a
JSON string, the already-decoded object (a list with one element), or a single
plan dict. No database connection is needed; the parser only reads the structure
Postgres documents. ``ANALYZE`` adds the actual times and row counts, and
``BUFFERS`` adds the block counts; the parser tolerates plans without them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


def _f(value):
    """Coerce to float, or None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class PlanNode:
    """One node of the execution plan, wrapping its raw attributes."""

    raw: dict
    children: tuple[PlanNode, ...] = ()
    path: tuple[int, ...] = ()

    # --- identity -------------------------------------------------------- #
    @property
    def node_type(self) -> str:
        return self.raw.get("Node Type", "?")

    @property
    def relation(self) -> str | None:
        return self.raw.get("Relation Name")

    @property
    def index_name(self) -> str | None:
        return self.raw.get("Index Name")

    @property
    def label(self) -> str:
        """A short human label, e.g. ``Seq Scan on orders``."""
        out = self.node_type
        if self.relation:
            out += f" on {self.relation}"
        elif self.index_name:
            out += f" using {self.index_name}"
        return out

    # --- estimates and actuals ------------------------------------------ #
    @property
    def plan_rows(self) -> float:
        return _f(self.raw.get("Plan Rows")) or 0.0

    @property
    def total_cost(self) -> float:
        return _f(self.raw.get("Total Cost")) or 0.0

    @property
    def has_actuals(self) -> bool:
        return "Actual Total Time" in self.raw or "Actual Rows" in self.raw

    @property
    def actual_rows(self) -> float | None:
        return _f(self.raw.get("Actual Rows"))

    @property
    def actual_loops(self) -> float:
        return _f(self.raw.get("Actual Loops")) or 1.0

    @property
    def actual_total_time(self) -> float | None:
        """Per-loop, inclusive of children (milliseconds)."""
        return _f(self.raw.get("Actual Total Time"))

    @property
    def inclusive_time(self) -> float | None:
        """Total time across all loops (per-loop time times loops)."""
        t = self.actual_total_time
        return None if t is None else t * self.actual_loops

    # --- the things rules look at --------------------------------------- #
    @property
    def rows_removed_by_filter(self) -> float | None:
        return _f(self.raw.get("Rows Removed by Filter"))

    @property
    def heap_fetches(self) -> float | None:
        return _f(self.raw.get("Heap Fetches"))

    @property
    def sort_method(self) -> str | None:
        return self.raw.get("Sort Method")

    @property
    def hash_batches(self) -> float | None:
        return _f(self.raw.get("Hash Batches"))

    @property
    def temp_written(self) -> float:
        return _f(self.raw.get("Temp Written Blocks")) or 0.0

    @property
    def shared_read(self) -> float:
        return _f(self.raw.get("Shared Read Blocks")) or 0.0

    @property
    def shared_hit(self) -> float:
        return _f(self.raw.get("Shared Hit Blocks")) or 0.0

    @property
    def spilled_to_disk(self) -> bool:
        method = (self.sort_method or "").lower()
        if "external" in method:               # external merge / external sort
            return True
        if (self.hash_batches or 0) > 1:        # hash join / aggregate spilled
            return True
        return self.temp_written > 0

    def walk(self):
        """Yield this node and all descendants, depth first."""
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass(frozen=True)
class Plan:
    """A parsed plan: the root node plus the run-level information."""

    root: PlanNode
    planning_time: float | None = None
    execution_time: float | None = None
    triggers: tuple[dict, ...] = ()
    settings: dict | None = None
    jit: dict | None = None
    raw: dict = field(default_factory=dict)

    @property
    def has_actuals(self) -> bool:
        return self.root.has_actuals

    def nodes(self):
        return list(self.root.walk())


def _build(node_dict: dict, path: tuple[int, ...]) -> PlanNode:
    children_raw = node_dict.get("Plans", []) or []
    children = tuple(_build(c, path + (i,)) for i, c in enumerate(children_raw))
    attrs = {k: v for k, v in node_dict.items() if k != "Plans"}
    return PlanNode(raw=attrs, children=children, path=path)


def parse(explain) -> Plan:
    """Parse ``EXPLAIN (FORMAT JSON)`` output into a :class:`Plan`.

    ``explain`` may be a JSON string, the decoded list, or a single plan dict.
    """
    if isinstance(explain, (bytes, bytearray)):
        explain = explain.decode("utf-8")
    if isinstance(explain, str):
        explain = json.loads(explain)
    if isinstance(explain, list):
        if not explain:
            raise ValueError("empty EXPLAIN output")
        explain = explain[0]
    if not isinstance(explain, dict):
        raise TypeError("expected EXPLAIN JSON (a dict, list or JSON string)")

    if "Plan" in explain:
        container, node = explain, explain["Plan"]
    elif "Node Type" in explain:
        container, node = {}, explain          # a bare plan node
    else:
        raise ValueError(
            "not an EXPLAIN plan: expected a 'Plan' key or a 'Node Type'. "
            "Use EXPLAIN (FORMAT JSON), not the text format.")

    root = _build(node, ())
    return Plan(
        root=root,
        planning_time=_f(container.get("Planning Time")),
        execution_time=_f(container.get("Execution Time")),
        triggers=tuple(container.get("Triggers", []) or ()),
        settings=container.get("Settings"),
        jit=container.get("JIT"),
        raw=container,
    )
