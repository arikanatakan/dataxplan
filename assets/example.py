"""Render the README example chart: the Bosch plan's self time per node.

Run:  python assets/example.py
"""

import json
import pathlib

import matplotlib
matplotlib.use("Agg")

import dataxplan

plan = json.loads(
    (pathlib.Path("examples") / "bosch_production_hash_join.json").read_text())
report = dataxplan.analyze(plan)
fig = dataxplan.plan_tree_chart(report)
fig.savefig("assets/example_bosch.png", dpi=140, bbox_inches="tight",
            facecolor="white")
print("wrote assets/example_bosch.png")
