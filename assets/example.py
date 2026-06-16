"""Render the README example charts: self time per node for each example plan.

Run:  python assets/example.py
"""

import json
import pathlib

import matplotlib
matplotlib.use("Agg")

import dataxplan

EXAMPLES = pathlib.Path("examples")
ASSETS = pathlib.Path("assets")

# example plan stem -> output image name, ordered largest scope to smallest
CHARTS = {
    "nyc_taxi_sort_spill": "example_nyc",
    "tpch_lineitem_filter": "example_tpch",
    "job_imdb_misestimate": "example_job",
    "bosch_production_hash_join": "example_bosch",
    "secom_semiconductor_index_only": "example_secom",
    "mercedes_automotive_lossy_bitmap": "example_mercedes",
    "garments_textile_seq_scan": "example_garments",
}

for stem, out in CHARTS.items():
    report = dataxplan.analyze(json.loads((EXAMPLES / f"{stem}.json").read_text()))
    fig = dataxplan.plan_tree_chart(report)
    fig.savefig(ASSETS / f"{out}.png", dpi=140, bbox_inches="tight",
                facecolor="white")
    print("wrote", out)
