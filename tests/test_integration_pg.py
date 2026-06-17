"""Validate parsing against real PostgreSQL EXPLAIN output, in every format.

Runs only when a database is available: set ``DATAXPLAN_PG_DSN`` and install
``psycopg``. CI provides both (see the integration job); locally these tests
skip, so no database is needed for the normal suite.
"""

import os

import pytest

psycopg = pytest.importorskip("psycopg")
DSN = os.environ.get("DATAXPLAN_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="set DATAXPLAN_PG_DSN to run")

import dataxplan  # noqa: E402

SQL = "SELECT count(*) FROM dxp_demo WHERE status = 7"


@pytest.fixture(scope="module")
def conn():
    connection = psycopg.connect(DSN)
    with connection.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS dxp_demo")
        cur.execute("CREATE TABLE dxp_demo (id int, status int, val text)")
        cur.execute("INSERT INTO dxp_demo "
                    "SELECT g, g % 1000, md5(g::text) "
                    "FROM generate_series(1, 200000) g")
        cur.execute("ANALYZE dxp_demo")
    connection.commit()
    yield connection
    with connection.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS dxp_demo")
    connection.commit()
    connection.close()


def _explain(connection, fmt: str):
    with connection.cursor() as cur:
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT {fmt}) {SQL}")
        rows = cur.fetchall()
    if fmt == "JSON":
        return rows[0][0]                       # psycopg decodes json for us
    return "\n".join(row[0] for row in rows)


@pytest.mark.parametrize("fmt", ["JSON", "TEXT", "YAML", "XML"])
def test_real_plan_parses_in_every_format(conn, fmt):
    report = dataxplan.analyze(_explain(conn, fmt))
    assert report.execution_time_ms is not None
    assert report.plan.nodes()
    assert report.has_node("Seq Scan", "dxp_demo") or report.has_node(
        "Index Scan", "dxp_demo")


def test_run_explain_helper(conn):
    report = dataxplan.analyze(dataxplan.run_explain(conn, SQL))
    assert report.execution_time_ms is not None
