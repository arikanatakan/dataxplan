"""Command-line interface: analyse a plan from a file or stdin.

    dataxplan plan.json
    dataxplan plan.json --tree
    dataxplan plan.json --json
    dataxplan before.json --compare after.json
    psql -XqAt -c "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ..." | dataxplan
"""

from __future__ import annotations

import argparse
import json
import sys

from . import analyze, compare, text_tree
from ._version import __version__


def _read(source: str) -> str:
    if source in (None, "-"):
        return sys.stdin.read()
    with open(source, encoding="utf-8") as handle:
        return handle.read()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="dataxplan",
        description="Analyse a PostgreSQL EXPLAIN (FORMAT JSON) plan, locally.")
    parser.add_argument("plan", nargs="?", default="-",
                        help="plan file, or - for stdin (the default)")
    parser.add_argument("--tree", action="store_true",
                        help="also print the annotated plan tree")
    parser.add_argument("--json", action="store_true",
                        help="print the full report (or comparison) as JSON")
    parser.add_argument("--compare", metavar="OTHER",
                        help="compare the plan against another plan file")
    parser.add_argument("--version", action="version",
                        version=f"dataxplan {__version__}")
    args = parser.parse_args(argv)

    try:
        plan = json.loads(_read(args.plan))
        if args.compare:
            result = compare(plan, json.loads(_read(args.compare)))
            print(json.dumps(result.to_dict(), indent=2, default=str)
                  if args.json else result.summary())
            return 0
        report = analyze(plan)
    except (ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"dataxplan: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(report.summary())
        if args.tree:
            print("\nplan tree:")
            print(text_tree(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
