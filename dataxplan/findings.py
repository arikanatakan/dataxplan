"""Heuristic rules that turn metrics into findings.

Each rule encodes a documented PostgreSQL behaviour and carries a ``reference``
to it (also tabulated in the README). A finding is an observation with an
explanation and, where reasonable, a suggestion; it is never a promise that a
change will help. When catalog context is supplied the messages are sharpened,
but every rule works from the plan alone.

Source basis (PostgreSQL manual unless noted):
  estimate_off            planner statistics, ANALYZE, CREATE STATISTICS;
                          Leis et al. (2015), the Join Order Benchmark study
  seq_scan_hot            Using EXPLAIN; the Indexes chapter
  disk_spill              work_mem (resource consumption)
  filter_discard          Using EXPLAIN (Rows Removed by Filter)
  nested_loop_blowup      planner join methods; Leis et al. (2015)
  index_only_heap_fetches Index-Only Scans and Covering Indexes
  lossy_bitmap            work_mem (lossy bitmap recheck)
  jit_overhead            Just-in-Time Compilation (jit_above_cost)
"""

from __future__ import annotations

from ._result import HIGH, INFO, LOW, MEDIUM, Finding
from .context import Context
from .metrics import NodeMetrics
from .parse import Plan, PlanNode

DEFAULT_THRESHOLDS = {
    "estimation_error_high": 100.0,   # x off -> high severity
    "estimation_error_med": 10.0,     # x off -> medium (if the node matters)
    "seq_scan_pct": 0.30,             # share of execution time
    "filter_discard_ratio": 10.0,     # rows removed vs rows kept
    "nested_loop_loops": 1000.0,      # inner executions
    "heap_fetch_ratio": 0.10,         # heap fetches vs rows
    "jit_pct": 0.25,                  # JIT time vs execution time
}

# The documented behaviour each rule relies on (see the README references).
_REF_STATS = ("PostgreSQL: planner statistics, ANALYZE, CREATE STATISTICS; "
              "Leis et al. (2015)")
_REF_EXPLAIN = "PostgreSQL: Using EXPLAIN; the Indexes chapter"
_REF_FILTER = "PostgreSQL: Using EXPLAIN (Rows Removed by Filter)"
_REF_WORKMEM = "PostgreSQL: work_mem (resource consumption)"
_REF_JOINS = "PostgreSQL: planner join methods; Leis et al. (2015)"
_REF_INDEX_ONLY = "PostgreSQL: Index-Only Scans and Covering Indexes"
_REF_JIT = "PostgreSQL: Just-in-Time Compilation (jit_above_cost)"


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.0f}%"


def run_findings(plan: Plan, metrics: list[NodeMetrics],
                 context: Context | None, thresholds: dict) -> list[Finding]:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    by_path: dict[tuple, PlanNode] = {n.path: n for n in plan.root.walk()}
    found: list[Finding] = []

    for m in metrics:
        node = by_path[m.path]
        ctx_table = context.table(m.relation) if context else None

        # 1. Row estimate far from reality (the usual root cause).
        if m.estimation_error is not None:
            sev = None
            if m.estimation_error >= t["estimation_error_high"]:
                sev = HIGH
            elif (m.estimation_error >= t["estimation_error_med"]
                  and (m.pct_self or 0) >= 0.10):
                sev = MEDIUM
            if sev:
                direction = "under" if (m.estimation_factor or 1) > 1 else "over"
                detail = (f"estimated {m.plan_rows:,.0f} rows, actual "
                          f"{m.actual_rows:,.0f} ({m.estimation_error:.0f}x "
                          f"{direction}-estimate)")
                sug = ("run ANALYZE on the table; if the columns are correlated "
                       "consider extended statistics (CREATE STATISTICS)")
                if ctx_table is not None and not ctx_table.analyzed:
                    sug = "statistics look stale; run ANALYZE on " + m.relation
                found.append(Finding("estimate_off", sev, "Row estimate is far off",
                                     detail, m.label, m.path, sug,
                                     reference=_REF_STATS))

        # 2. Sequential scan taking a large share of the time.
        if (m.node_type == "Seq Scan" and m.relation
                and (m.pct_self or 0) >= t["seq_scan_pct"]):
            size = (f" ({ctx_table.row_count:,.0f} rows)"
                    if ctx_table and ctx_table.row_count else "")
            detail = (f"sequential scan{size} is {_pct(m.pct_self)} of execution "
                      f"time, reading {m.actual_rows:,.0f} rows"
                      if m.actual_rows is not None else
                      f"sequential scan{size} is {_pct(m.pct_self)} of execution time")
            sug = f"consider an index supporting the filter or join on {m.relation}"
            if ctx_table is not None and ctx_table.indexed_columns:
                sug += (f" (existing indexes cover: "
                        f"{', '.join(ctx_table.indexed_columns)})")
            found.append(Finding("seq_scan_hot", HIGH, "Hot sequential scan",
                                 detail, m.label, m.path, sug,
                                 reference=_REF_EXPLAIN))

        # 3. A sort or hash spilled to disk.
        if m.spilled:
            if node.sort_method and "external" in node.sort_method.lower():
                what = f"sort spilled to disk ({node.sort_method})"
            elif (node.hash_batches or 0) > 1:
                what = f"hash spilled to disk ({node.hash_batches:.0f} batches)"
            else:
                what = f"wrote {node.temp_written:,.0f} temp blocks to disk"
            mem = (f"; work_mem is {context.work_mem_mb:.0f} MB"
                   if context and context.work_mem_mb else "")
            found.append(Finding(
                "disk_spill", MEDIUM, "Operation spilled to disk",
                what + mem, m.label, m.path,
                "raise work_mem for this query, or reduce the rows being "
                "sorted or hashed", reference=_REF_WORKMEM))

        # 4. Reading many rows and discarding most (non-sargable / missing index).
        removed = m.rows_removed_by_filter
        if (removed is not None and m.actual_rows is not None
                and removed >= t["filter_discard_ratio"] * (m.actual_rows + 1)
                and "Scan" in m.node_type):
            detail = (f"removed {removed:,.0f} rows by filter but kept only "
                      f"{m.actual_rows:,.0f}")
            found.append(Finding(
                "filter_discard", MEDIUM, "Filter discards most rows read", detail,
                m.label, m.path,
                "the predicate is not selective via the current access path; an "
                "index on the filtered column may help", reference=_REF_FILTER))

        # 5. Nested loop driving its inner side many times.
        if m.node_type == "Nested Loop" and node.children:
            inner_loops = max((c.actual_loops for c in node.children), default=0)
            if inner_loops >= t["nested_loop_loops"]:
                found.append(Finding(
                    "nested_loop_blowup", MEDIUM, "Nested loop with many iterations",
                    f"the inner side executed {inner_loops:,.0f} times", m.label,
                    m.path,
                    "usually an under-estimate upstream; check the row estimates, a "
                    "hash or merge join may be cheaper", reference=_REF_JOINS))

        # 6. Index-only scan still hitting the heap (visibility map not set).
        if (m.node_type == "Index Only Scan" and m.heap_fetches
                and m.actual_rows is not None
                and m.heap_fetches >= t["heap_fetch_ratio"] * (m.actual_rows + 1)):
            found.append(Finding(
                "index_only_heap_fetches", LOW,
                "Index-only scan with many heap fetches",
                f"{m.heap_fetches:,.0f} heap fetches for {m.actual_rows:,.0f} rows",
                m.label, m.path,
                "VACUUM the table so the visibility map lets the scan skip the heap",
                reference=_REF_INDEX_ONLY))

        # 7. Lossy bitmap heap scan (work_mem too small for the bitmap).
        recheck = node.raw.get("Rows Removed by Index Recheck")
        if m.node_type == "Bitmap Heap Scan" and recheck:
            found.append(Finding(
                "lossy_bitmap", LOW, "Bitmap heap scan went lossy",
                f"{float(recheck):,.0f} rows rechecked after a lossy bitmap",
                m.label, m.path,
                "raise work_mem so the bitmap stays exact", reference=_REF_WORKMEM))

    # 8. JIT overhead on a short query.
    jit = plan.jit
    if jit and plan.execution_time:
        total = (jit.get("Timing", {}) or {}).get("Total")
        if total and plan.execution_time and total >= t["jit_pct"] * plan.execution_time:
            found.append(Finding(
                "jit_overhead", LOW, "JIT compilation is a large share of the time",
                f"JIT took {total:,.1f} ms of {plan.execution_time:,.1f} ms total",
                None, None,
                "for short, frequent queries consider raising jit_above_cost or "
                "turning JIT off", reference=_REF_JIT))

    if not found:
        found.append(Finding("clean", INFO, "No issues flagged",
                             "no heuristic flagged this plan", None, None, None))

    found.sort(key=lambda f: (f.rank, -(_self_pct(metrics, f.path))))
    return found


def _self_pct(metrics: list[NodeMetrics], path) -> float:
    if path is None:
        return 0.0
    for m in metrics:
        if m.path == path:
            return m.pct_self or 0.0
    return 0.0
