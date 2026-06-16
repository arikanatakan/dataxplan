import dataxplan
from dataxplan import Context, TableInfo


def test_context_sharpens_seq_scan(load):
    ctx = Context(tables={
        "orders": TableInfo("orders", row_count=10_000_000, indexed_columns=("id",))})
    r = dataxplan.analyze(load("seq_scan_filter.json"), context=ctx)
    seq = next(f for f in r.findings if f.id == "seq_scan_hot")
    assert "10,000,000 rows" in seq.detail
    assert "id" in (seq.suggestion or "")


def test_context_from_mapping(load):
    r = dataxplan.analyze(load("seq_scan_filter.json"),
                          context={"tables": {"orders": {"row_count": 5}}})
    assert r.has_finding("seq_scan_hot")


def test_stale_stats_changes_suggestion(load):
    ctx = Context(tables={"a": TableInfo("a", analyzed=False)})
    r = dataxplan.analyze(load("misestimate_nestloop.json"), context=ctx)
    est = next(f for f in r.findings
               if f.id == "estimate_off" and f.node == "Index Scan on a")
    assert "stale" in (est.suggestion or "")
