"""The top-level analysis: ``analyze`` ties parsing, metrics and findings into a
``Report``. The report carries a small assertion API so a query plan can be
guarded in a test suite (fail the build if a change makes the plan regress).
"""

from __future__ import annotations

from dataclasses import dataclass

from ._result import HIGH, MEDIUM, Finding, make_meta, ms
from .context import Context, as_context
from .findings import run_findings
from .metrics import NodeMetrics, compute_metrics, rollups
from .parse import Plan, parse


@dataclass(frozen=True)
class Report:
    """Everything dataxplan derives from one plan."""

    plan: Plan
    metrics: tuple[NodeMetrics, ...]
    rollup: dict
    findings: tuple[Finding, ...]
    meta: dict

    # --- assertion API (for tests and CI) -------------------------------- #
    @property
    def execution_time_ms(self) -> float | None:
        return self.plan.execution_time

    @property
    def max_estimation_error(self) -> float:
        return self.rollup.get("max_estimation_error") or 1.0

    @property
    def spilled_to_disk(self) -> bool:
        return bool(self.rollup.get("spilled_to_disk"))

    @property
    def ok(self) -> bool:
        """True when nothing high-severity was flagged."""
        return not any(f.severity == HIGH for f in self.findings)

    def has_node(self, node_type: str, relation: str | None = None) -> bool:
        for n in self.plan.root.walk():
            if n.node_type == node_type and (relation is None or n.relation == relation):
                return True
        return False

    def has_seq_scan_on(self, relation: str) -> bool:
        return self.has_node("Seq Scan", relation)

    def has_finding(self, finding_id: str) -> bool:
        return any(f.id == finding_id for f in self.findings)

    def findings_at_least(self, severity: str = MEDIUM) -> list[Finding]:
        cutoff = Finding("", severity, "", "").rank
        return [f for f in self.findings if f.rank <= cutoff]

    # --- presentation ---------------------------------------------------- #
    def summary(self) -> str:
        r = self.rollup
        lines = [f"dataxplan - {self.meta.get('computed_at', '')}"]
        if r.get("execution_time_ms") is not None:
            lines.append(f"  execution time   {ms(r['execution_time_ms'])}"
                         f"   (planning {ms(r.get('planning_time_ms'))})")
        else:
            lines.append("  plan only (no ANALYZE; run EXPLAIN ANALYZE for timing)")
        lines.append(f"  nodes {r['node_count']}, depth {r['max_depth']}")
        if r.get("max_estimation_error"):
            lines.append(f"  worst row estimate   {r['max_estimation_error']:.0f}x off")
        lines.append(f"  spilled to disk      {'yes' if r['spilled_to_disk'] else 'no'}")
        if r.get("parallel"):
            lines.append("  note: parallel plan, so self times are total work "
                         "across workers, not wall-clock time")
        if r.get("top_self_time") and r["top_self_time"][0]["self_time_ms"] is not None:
            lines.append("  top by self time:")
            for e in r["top_self_time"]:
                pct = "" if e["pct_self"] is None else f" ({100 * e['pct_self']:.0f}%)"
                lines.append(f"    {e['label']:<32} {ms(e['self_time_ms'])}{pct}")
        lines.append("findings:")
        for f in self.findings:
            lines.append("  " + str(f).replace("\n", "\n  "))
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "schema": 1,
            "summary_metrics": self.rollup,
            "nodes": [m.to_dict() for m in self.metrics],
            "findings": [f.to_dict() for f in self.findings],
            "meta": self.meta,
        }


def analyze(explain, context=None, *, thresholds: dict | None = None) -> Report:
    """Analyse one ``EXPLAIN (FORMAT JSON)`` plan.

    ``explain`` is the EXPLAIN output (JSON string, list or dict). ``context`` is
    an optional :class:`~dataxplan.context.Context` (or mapping) with catalog
    metadata that sharpens the findings. ``thresholds`` overrides the rule cut-offs.
    """
    plan: Plan = parse(explain)
    ctx: Context | None = as_context(context)
    metrics = compute_metrics(plan)
    roll = rollups(plan, metrics)
    findings = run_findings(plan, metrics, ctx, thresholds or {})
    meta = make_meta({"node_count": len(metrics),
                      "execution_time_ms": plan.execution_time,
                      "has_context": ctx is not None})
    return Report(plan, tuple(metrics), roll, tuple(findings), meta)


__all__ = ["Report", "analyze"]
