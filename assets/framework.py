"""Generate the dataxplan framework figure (academic style).

Top: an EXPLAIN plan flows through parse, metrics and findings into a Report.
Bottom: what you do with it.
Run:  python assets/framework.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5})

INK = "#1f2d3d"
MUT = "#5b6b7b"
NEUT_F, NEUT_E = "#eef1f4", "#9aa7b3"
ANA_F, ANA_E = "#eef3f8", "#3b6ea5"
RES_F, RES_E = "#d4e4f4", "#2c5f8a"
OPT_F, OPT_E = "#e3f1ec", "#3a8f78"
CONT_F, CONT_E = "#f7f9fb", "#c9d2db"
BAN_F, BAN_E = "#f5f7f9", "#cdd6df"
ARROW = "#7c8a99"

fig, ax = plt.subplots(figsize=(12, 7.0))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")


def box(x, y, w, h, text, fill, edge, fs=8.2, bold=False, tcol=INK):
    ax.add_patch(FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.35,rounding_size=1.4",
        linewidth=1.25, edgecolor=edge, facecolor=fill, zorder=2))
    ax.text(x, y, text, ha="center", va="center", color=tcol, fontsize=fs,
            fontweight="bold" if bold else "normal", zorder=5)


def arrow(x0, y0, x1, y1, color=ARROW, lw=1.15):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=1,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                shrinkA=1, shrinkB=1))


ax.text(3, 97.5, "dataxplan", fontsize=13.5, fontweight="bold", color=INK, ha="left")
ax.text(3, 93.5, "read PostgreSQL EXPLAIN plans, locally", fontsize=9.5, color=MUT,
        ha="left", fontstyle="italic")

# ---- Top tier: input -> engine -> report -----------------------------------
for x, t in [(12, "Input"), (40, "Engine"), (75, "Report")]:
    ax.text(x, 89, t, ha="center", fontsize=9.3, color=MUT, fontstyle="italic")

box(12, 81, 19, 8, "EXPLAIN\n(FORMAT JSON)", NEUT_F, NEUT_E, fs=7.9)
box(12, 68, 19, 8, "+ optional\ncatalog context", NEUT_F, NEUT_E, fs=7.9)

ax.add_patch(FancyBboxPatch((24, 57), 31, 35,
             boxstyle="round,pad=0.4,rounding_size=1.6",
             linewidth=1.3, edgecolor=CONT_E, facecolor=CONT_F, zorder=0))
for y, t in [(84, "parse       EXPLAIN JSON -> plan tree"),
             (73, "metrics     self-time · est. error · spills"),
             (62, "findings    documented heuristic rules")]:
    box(40, y, 29, 7.2, t, ANA_F, ANA_E, fs=7.3)

box(75, 71, 22, 31,
    "Report\n\nsummary · findings\nassertions (CI)\nto_dict (JSON)\n\n"
    "meta: version · hash",
    RES_F, RES_E, fs=8.0, bold=True)

for y in (81, 68):
    arrow(21.7, y, 23.6, 71)
arrow(55.2, 71, 63.8, 71)

# ---- Bottom tier: what you do with it --------------------------------------
ax.text(50, 46, "What you do with it", ha="center", fontsize=11.5,
        fontweight="bold", color=INK)

band = [(13, "assert in CI\n(guard the plan)"), (37, "compare plans\n(regression)"),
        (61, "text tree\n(annotated)"), (85, "self-time chart\n(viz)")]
for x, t in band:
    box(x, 32, 19, 10, t, OPT_F, OPT_E, fs=7.9)

box(50, 12, 90, 8,
    "no database connection      ·      deterministic\n"
    "findings are documented heuristics, not guarantees",
    BAN_F, BAN_E, fs=7.9, tcol=MUT)

fig.savefig("assets/framework.png", dpi=200, bbox_inches="tight",
            facecolor="white")
print("wrote assets/framework.png")
