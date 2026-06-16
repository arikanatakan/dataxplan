"""Optional convenience: fetch a plan from a database connection you already
have. dataxplan does not depend on any driver; you pass a DB-API connection
(psycopg, psycopg2, ...) and dataxplan only calls ``cursor.execute`` on it.

WARNING: with ``analyze=True`` (the default) the query is actually executed, so
it runs side effects and takes real time. Use ``analyze=False`` for a plan-only
estimate, and run inside a transaction you control for write statements.
"""

from __future__ import annotations

import json


def run_explain(connection, sql, *, params=None, analyze: bool = True,
                buffers: bool = True, settings: bool = False) -> list:
    """Run ``EXPLAIN (FORMAT JSON, ...)`` for ``sql`` and return the decoded plan.

    Pass the result to :func:`dataxplan.analyze`. ``BUFFERS`` is only added when
    ``analyze`` is on.
    """
    options = ["FORMAT JSON"]
    if analyze:
        options.append("ANALYZE")
        if buffers:
            options.append("BUFFERS")
    if settings:
        options.append("SETTINGS")
    statement = f"EXPLAIN ({', '.join(options)}) {sql}"

    cursor = connection.cursor()
    try:
        cursor.execute(statement, params)
        row = cursor.fetchone()
    finally:
        cursor.close()
    if not row:
        raise ValueError("EXPLAIN returned no rows")

    data = row[0]
    if isinstance(data, (str, bytes, bytearray)):
        data = json.loads(data)
    return data
