import json

import dataxplan


class FakeCursor:
    def __init__(self, result):
        self.result = result
        self.executed = None
        self.params = None

    def execute(self, sql, params=None):
        self.executed = sql
        self.params = params

    def fetchone(self):
        return [self.result]

    def close(self):
        pass


class FakeConnection:
    def __init__(self, result):
        self.cur = FakeCursor(result)

    def cursor(self):
        return self.cur


def test_run_explain_builds_statement_and_returns_plan():
    plan = [{"Plan": {"Node Type": "Result", "Plan Rows": 1}}]
    conn = FakeConnection(plan)
    out = dataxplan.run_explain(conn, "SELECT 1")
    assert out == plan
    assert conn.cur.executed.startswith("EXPLAIN (FORMAT JSON, ANALYZE, BUFFERS) ")
    assert conn.cur.executed.endswith("SELECT 1")


def test_run_explain_plan_only_omits_analyze():
    conn = FakeConnection([{"Plan": {"Node Type": "Result"}}])
    dataxplan.run_explain(conn, "SELECT 1", analyze=False)
    assert "ANALYZE" not in conn.cur.executed
    assert "BUFFERS" not in conn.cur.executed


def test_run_explain_parses_json_string():
    conn = FakeConnection(json.dumps([{"Plan": {"Node Type": "Result"}}]))
    out = dataxplan.run_explain(conn, "SELECT 1")
    assert out[0]["Plan"]["Node Type"] == "Result"


def test_run_explain_feeds_analyze():
    plan = [{"Plan": {"Node Type": "Seq Scan", "Relation Name": "t",
                      "Plan Rows": 1, "Actual Total Time": 1.0, "Actual Rows": 1,
                      "Actual Loops": 1}, "Execution Time": 1.0}]
    report = dataxplan.analyze(dataxplan.run_explain(FakeConnection(plan), "SELECT 1"))
    assert report.execution_time_ms == 1.0
