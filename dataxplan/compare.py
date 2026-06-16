"""Compare two plans for regression: did a change make a query slower, change
its shape, or worsen its estimates? Useful before/after an index, a query
rewrite or a schema change, and as a guard in CI.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._result import make_meta, ms
from .report import Report, analyze


def _as_report(x) -> Report:
    return x if isinstance(x, Report) else analyze(x)


def _self_by_label(report: Report) -> dict:
    out: dict = {}
    for m in report.metrics:
        out[m.label] = out.get(m.label, 0.0) + (m.self_time or 0.0)
    return out


@dataclass(frozen=True)
class Comparison:
    before_time_ms: float | None
    after_time_ms: float | None
    delta_ms: float | None
    delta_pct: float | None
    node_deltas: tuple[dict, ...]
    appeared: tuple[str, ...]
    disappeared: tuple[str, ...]
    new_findings: tuple[str, ...]
    resolved_findings: tuple[str, ...]
    before_max_error: float
    after_max_error: float
    verdict: str            # improved | regressed | similar
    meta: dict

    def summary(self) -> str:
        lines = [f"dataxplan compare - {self.verdict.upper()}"]
        if self.before_time_ms is not None and self.after_time_ms is not None:
            d = "" if self.delta_pct is None else f" ({self.delta_pct:+.0%})"
            lines.append(f"  execution time   {ms(self.before_time_ms)} -> "
                         f"{ms(self.after_time_ms)}{d}")
        if self.appeared:
            lines.append(f"  new nodes        {', '.join(self.appeared)}")
        if self.disappeared:
            lines.append(f"  gone nodes       {', '.join(self.disappeared)}")
        if self.new_findings:
            lines.append(f"  new findings     {', '.join(self.new_findings)}")
        if self.resolved_findings:
            lines.append(f"  resolved         {', '.join(self.resolved_findings)}")
        big = [d for d in self.node_deltas if abs(d["delta_ms"] or 0) > 0][:5]
        if big:
            lines.append("  largest self-time changes:")
            for d in big:
                lines.append(f"    {d['label']:<32} {d['delta_ms']:+,.2f} ms")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "schema": 1, "verdict": self.verdict,
            "before_time_ms": self.before_time_ms, "after_time_ms": self.after_time_ms,
            "delta_ms": self.delta_ms, "delta_pct": self.delta_pct,
            "node_deltas": list(self.node_deltas), "appeared": list(self.appeared),
            "disappeared": list(self.disappeared),
            "new_findings": list(self.new_findings),
            "resolved_findings": list(self.resolved_findings),
            "before_max_error": self.before_max_error,
            "after_max_error": self.after_max_error, "meta": self.meta,
        }


def compare(before, after) -> Comparison:
    """Compare two plans (``Report`` objects or raw EXPLAIN output)."""
    a, b = _as_report(before), _as_report(after)
    bt, at = a.execution_time_ms, b.execution_time_ms

    delta = dpct = None
    if bt is not None and at is not None:
        delta = at - bt
        dpct = (delta / bt) if bt else None
        threshold = 0.05 * bt
        verdict = ("regressed" if delta > threshold
                   else "improved" if delta < -threshold else "similar")
    else:
        bc, ac = a.plan.root.total_cost, b.plan.root.total_cost
        verdict = ("regressed" if ac > 1.05 * bc
                   else "improved" if ac < 0.95 * bc else "similar")

    sb, sa = _self_by_label(a), _self_by_label(b)
    labels = sorted(set(sb) | set(sa))
    node_deltas = tuple(sorted(
        ({"label": lb, "before_ms": sb.get(lb), "after_ms": sa.get(lb),
          "delta_ms": (sa.get(lb, 0.0) - sb.get(lb, 0.0))} for lb in labels),
        key=lambda d: abs(d["delta_ms"] or 0), reverse=True))

    before_labels = {m.label for m in a.metrics}
    after_labels = {m.label for m in b.metrics}
    bf = {f.id for f in a.findings if f.id != "clean"}
    af = {f.id for f in b.findings if f.id != "clean"}

    return Comparison(
        before_time_ms=bt, after_time_ms=at, delta_ms=delta, delta_pct=dpct,
        node_deltas=node_deltas,
        appeared=tuple(sorted(after_labels - before_labels)),
        disappeared=tuple(sorted(before_labels - after_labels)),
        new_findings=tuple(sorted(af - bf)),
        resolved_findings=tuple(sorted(bf - af)),
        before_max_error=a.max_estimation_error,
        after_max_error=b.max_estimation_error,
        verdict=verdict,
        meta=make_meta({"before_time": bt, "after_time": at}))
