"""Parse PostgreSQL ``EXPLAIN`` output into a typed plan tree.

The input is whatever ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ...`` returns: a
JSON string, the already-decoded object (a list with one element), or a single
plan dict. The ``FORMAT TEXT`` (the default), ``YAML`` and ``XML`` outputs are
also accepted and auto-detected; JSON, YAML and XML are exact, while the text
format is parsed best-effort. No database connection is needed; the parser only
reads the structure Postgres documents. ``ANALYZE`` adds the actual times and
row counts, and ``BUFFERS`` adds the block counts; plans without them are
tolerated.

YAML input needs PyYAML (``dataxplan[yaml]``); XML uses the standard library.
"""

from __future__ import annotations

import json
import re
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
    """Parse ``EXPLAIN`` output into a :class:`Plan`.

    ``explain`` may be a decoded object (list or dict) or a string in any of the
    EXPLAIN formats: JSON, text, YAML or XML (auto-detected).
    """
    if isinstance(explain, (bytes, bytearray)):
        explain = explain.decode("utf-8")
    if isinstance(explain, str):
        explain = _from_string(explain)
    if isinstance(explain, list):
        if not explain:
            raise ValueError("empty EXPLAIN output")
        explain = explain[0]
    if not isinstance(explain, dict):
        raise TypeError("expected an EXPLAIN plan (a dict, list, or a JSON, "
                        "text, YAML or XML string)")

    if "Plan" in explain:
        container, node = explain, explain["Plan"]
    elif "Node Type" in explain:
        container, node = {}, explain          # a bare plan node
    else:
        raise ValueError(
            "not an EXPLAIN plan: expected a 'Plan' key or a 'Node Type'")

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


# --------------------------------------------------------------------------- #
# Format detection and the non-JSON formats
# --------------------------------------------------------------------------- #
_NODE_RE = re.compile(
    r"^(?P<indent>\s*)(?:->\s+)?(?P<body>.+?)\s+"
    r"\(cost=(?P<sc>[\d.]+)\.\.(?P<tc>[\d.]+)\s+rows=(?P<pr>\d+)\s+width=(?P<w>\d+)\)"
    r"(?:\s+\(actual time=(?P<ast>[\d.]+)\.\.(?P<att>[\d.]+)\s+rows=(?P<ar>\d+)"
    r"\s+loops=(?P<al>\d+)\))?")
_PROP_RE = re.compile(r"^\s*(?P<key>[A-Z][\w /-]*?):\s*(?P<val>.*\S)\s*$")
_TIME_RE = re.compile(r"^\s*(Planning|Execution) Time:\s*([\d.]+)\s*ms\s*$")


def _from_string(text: str):
    """Detect the EXPLAIN format of a string and return its decoded object."""
    stripped = text.lstrip()
    if not stripped:
        raise ValueError("empty EXPLAIN output")
    first = stripped[0]
    if first in "[{":
        return json.loads(text)
    if first == "<":
        return _from_xml(text)
    if stripped.startswith("- "):
        return _from_yaml(text)
    return _from_text(text)


def _from_yaml(text: str):
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised only without PyYAML
        raise ImportError("YAML EXPLAIN output needs PyYAML; install "
                          "dataxplan[yaml], or use EXPLAIN (FORMAT JSON)") from exc
    return yaml.safe_load(text)


def _local(tag: str) -> str:
    return tag.rpartition("}")[2]


def _xml_to_dict(elem) -> dict:
    out: dict = {}
    for child in elem:
        tag = _local(child.tag).replace("-", " ")
        if tag == "Plans":
            out["Plans"] = [_xml_to_dict(p) for p in child]
        elif len(child):
            out[tag] = _xml_to_dict(child)
        else:
            out[tag] = child.text
    return out


def _from_xml(text: str) -> dict:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)
    for elem in root.iter():
        if _local(elem.tag) == "Query":
            return _xml_to_dict(elem)
    raise ValueError("could not find a <Query> in the XML EXPLAIN output")


def _node_identity(body: str) -> dict:
    """Split a text node header into Node Type, relation and index."""
    out: dict = {}
    if " using " in body:
        node_type, rest = body.split(" using ", 1)
        if " on " in rest:
            index, relation = rest.split(" on ", 1)
            out["Index Name"] = index.strip()
            out["Relation Name"] = relation.split()[0]
        else:
            out["Index Name"] = rest.strip()
        out["Node Type"] = node_type.strip()
    elif " on " in body:
        node_type, relation = body.split(" on ", 1)
        out["Node Type"] = node_type.strip()
        out["Relation Name"] = relation.split()[0]
    else:
        out["Node Type"] = body.strip()
    return out


def _parse_buffers(node: dict, value: str) -> None:
    for clause in value.split(","):
        words = clause.split()
        prefix = {"shared": "Shared", "temp": "Temp",
                  "local": "Local"}.get(words[0].lower()) if words else None
        if not prefix:
            continue
        for hit in re.finditer(r"(hit|read|written|dirtied)=(\d+)", clause):
            node[f"{prefix} {hit.group(1).capitalize()} Blocks"] = int(hit.group(2))


def _apply_property(node: dict, line: str) -> None:
    match = _PROP_RE.match(line)
    if not match:
        return
    key, value = match.group("key").strip(), match.group("val").strip()
    if key == "Buffers":
        _parse_buffers(node, value)
    elif "Batches:" in line:
        for name in ("Buckets", "Batches"):
            hit = re.search(name + r":\s*(\d+)", line)
            if hit:
                node["Hash " + name] = int(hit.group(1))
    elif key in ("Rows Removed by Filter", "Heap Fetches",
                 "Rows Removed by Index Recheck"):
        digits = re.match(r"\d+", value)
        node[key] = int(digits.group()) if digits else value
    else:
        node[key] = value


def _from_text(text: str) -> dict:
    """Parse the human-readable ``EXPLAIN`` text format (best-effort)."""
    container: dict = {}
    root = None
    stack: list = []                       # (indent, node) from root downwards
    for line in text.splitlines():
        if not line.strip():
            continue
        timing = _TIME_RE.match(line)
        if timing:
            container[timing.group(1) + " Time"] = float(timing.group(2))
            continue
        node_match = _NODE_RE.match(line)
        if node_match:
            node: dict = {"Plans": []}
            node.update(_node_identity(node_match.group("body").strip()))
            node["Startup Cost"] = float(node_match.group("sc"))
            node["Total Cost"] = float(node_match.group("tc"))
            node["Plan Rows"] = int(node_match.group("pr"))
            node["Plan Width"] = int(node_match.group("w"))
            if node_match.group("ar") is not None:
                node["Actual Startup Time"] = float(node_match.group("ast"))
                node["Actual Total Time"] = float(node_match.group("att"))
                node["Actual Rows"] = int(node_match.group("ar"))
                node["Actual Loops"] = int(node_match.group("al"))
            indent = len(node_match.group("indent"))
            while stack and stack[-1][0] >= indent:
                stack.pop()
            if stack:
                stack[-1][1]["Plans"].append(node)
            else:
                root = node
            stack.append((indent, node))
        elif stack:
            _apply_property(stack[-1][1], line)

    if root is None:
        raise ValueError("could not parse a text plan; use EXPLAIN (FORMAT JSON) "
                         "for exact results")
    container["Plan"] = root
    return container
