"""Shared plumbing: provenance (version, input hash, timestamp), the ``Finding``
type, and small formatting helpers. Every public result carries a meta block so
an analysis can be reproduced and audited later.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from ._version import __version__

SCHEMA = 1

# Finding severities, most to least serious.
HIGH = "high"
MEDIUM = "medium"
LOW = "low"
INFO = "info"
_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_hash(obj: object) -> str:
    payload = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()[:16]


def make_meta(inputs: dict) -> dict:
    """The provenance block stamped onto every result."""
    return {
        "library": "dataxplan",
        "version": __version__,
        "computed_at": utcnow(),
        "input_hash": data_hash(inputs),
    }


@dataclass(frozen=True)
class Finding:
    """One observation about a plan: a documented heuristic, not a guarantee."""

    id: str
    severity: str           # high | medium | low | info
    title: str
    detail: str
    node: str | None = None         # e.g. "Seq Scan on orders"
    path: tuple[int, ...] | None = None
    suggestion: str | None = None

    @property
    def rank(self) -> int:
        return _ORDER.get(self.severity, 9)

    def __str__(self) -> str:
        head = f"[{self.severity.upper()}] {self.title}"
        if self.node:
            head += f"  ({self.node})"
        lines = [head, f"    {self.detail}"]
        if self.suggestion:
            lines.append(f"    -> {self.suggestion}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "severity": self.severity, "title": self.title,
            "detail": self.detail, "node": self.node,
            "path": list(self.path) if self.path else None,
            "suggestion": self.suggestion,
        }


def ms(value: float | None) -> str:
    return "-" if value is None else f"{value:,.2f} ms"


def num(value: float | None, places: int = 0) -> str:
    return "-" if value is None else f"{value:,.{places}f}"
