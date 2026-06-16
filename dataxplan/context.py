"""Optional catalog context.

The core analysis works from the plan alone. When the caller can supply a little
metadata from the database catalog (table sizes, the columns that are indexed,
the server's ``work_mem``), the findings get sharper: a sequential scan on a
known-large table with no index on the filtered column is a stronger signal than
a sequential scan in isolation. Context is data the caller provides; the library
never connects to a database to fetch it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TableInfo:
    """What we may know about one table."""

    name: str
    row_count: float | None = None
    indexed_columns: tuple[str, ...] = ()      # columns that appear in some index
    analyzed: bool = True                       # False if statistics look stale

    def has_index_on(self, column: str) -> bool:
        return column in self.indexed_columns


@dataclass(frozen=True)
class Context:
    """Catalog metadata the caller knows, keyed by table name."""

    tables: dict = field(default_factory=dict)   # name -> TableInfo
    work_mem_mb: float | None = None

    def table(self, name: str | None) -> TableInfo | None:
        if name is None:
            return None
        return self.tables.get(name)


def as_context(value) -> Context | None:
    """Accept a :class:`Context`, a mapping, or None."""
    if value is None or isinstance(value, Context):
        return value
    if isinstance(value, Mapping):
        tables = {}
        raw_tables = value.get("tables", {})
        for name, info in raw_tables.items():
            if isinstance(info, TableInfo):
                tables[name] = info
            elif isinstance(info, Mapping):
                tables[name] = TableInfo(
                    name=name,
                    row_count=info.get("row_count"),
                    indexed_columns=tuple(info.get("indexed_columns", ())),
                    analyzed=info.get("analyzed", True))
            else:
                raise TypeError(f"table info for '{name}' must be a mapping")
        return Context(tables=tables, work_mem_mb=value.get("work_mem_mb"))
    raise TypeError("context must be a Context, a mapping, or None")
