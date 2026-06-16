"""Render a plan: an annotated text tree (dependency-free) and an optional
self-time bar chart (needs matplotlib, ``dataxplan[viz]``).
"""

from __future__ import annotations

from .report import Report

INK = "#1f2d3d"
MUT = "#5b6b7b"
BAR = "#3b6ea5"
HOT = "#c0392b"
GRID = "#dce3ea"


def text_tree(report: Report) -> str:
    """An indented plan tree annotated with self time, rows and flags."""
    by_path = {m.path: m for m in report.metrics}
    lines: list[str] = []

    def rec(node, depth: int) -> None:
        m = by_path[node.path]
        parts = [node.label]
        if m.self_time is not None:
            pct = "" if m.pct_self is None else f"/{100 * m.pct_self:.0f}%"
            parts.append(f"self {m.self_time:.1f}ms{pct}")
        if m.actual_rows is not None:
            parts.append(f"rows {m.plan_rows:.0f}->{m.actual_rows:.0f}")
            if m.estimation_error and m.estimation_error >= 10:
                parts.append(f"[{m.estimation_error:.0f}x off]")
        if m.spilled:
            parts.append("[spill]")
        lines.append("  " * depth + "- " + "  ".join(parts))
        for child in node.children:
            rec(child, depth + 1)

    rec(report.plan.root, 0)
    return "\n".join(lines)


def plan_tree_chart(report: Report, *, ax=None):
    """Self time per node as an indented horizontal bar chart.

    Nodes flagged at high severity are drawn in a warning colour. Needs
    matplotlib (``pip install dataxplan[viz]``).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError("the chart needs matplotlib; install dataxplan[viz]") from exc

    nodes = report.plan.nodes()
    by_path = {m.path: m for m in report.metrics}
    hot_paths = {f.path for f in report.findings if f.severity == "high" and f.path}

    labels, values, colours = [], [], []
    for n in nodes:
        m = by_path[n.path]
        labels.append("  " * len(n.path) + n.label)
        values.append(m.self_time or 0.0)
        colours.append(HOT if n.path in hot_paths else BAR)

    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8.5, 0.45 * len(nodes) + 1.2))
    y = range(len(nodes))
    ax.barh(list(y), values, color=colours, edgecolor=INK, linewidth=0.5, height=0.7)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=8, fontfamily="monospace")
    ax.invert_yaxis()
    ax.set_xlabel("self time (ms)")
    title = "query plan - self time by node"
    if report.execution_time_ms is not None:
        title += f"  (total {report.execution_time_ms:,.0f} ms)"
    ax.set_title(title, color=INK, fontsize=11, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUT)
    ax.tick_params(colors=MUT)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    if fig is not None:
        fig.tight_layout()
    return fig if fig is not None else ax.figure
