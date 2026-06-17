import dataxplan


def _ids(report):
    return {f.id for f in report.findings}


def test_hot_seq_scan_and_filter_discard(load):
    ids = _ids(dataxplan.analyze(load("seq_scan_filter.json")))
    assert "seq_scan_hot" in ids
    assert "filter_discard" in ids


def test_misestimate_and_nested_loop(load):
    ids = _ids(dataxplan.analyze(load("misestimate_nestloop.json")))
    assert "estimate_off" in ids
    assert "nested_loop_blowup" in ids


def test_disk_spill(load):
    assert "disk_spill" in _ids(dataxplan.analyze(load("sort_spill.json")))


def test_clean_plan_has_only_info(load):
    r = dataxplan.analyze(load("clean.json"))
    assert _ids(r) == {"clean"}
    assert r.ok


def test_findings_sorted_high_first(load):
    findings = dataxplan.analyze(load("seq_scan_filter.json")).findings
    assert findings[0].severity == "high"


def test_severity_high_seq_scan(load):
    seq = next(f for f in dataxplan.analyze(load("seq_scan_filter.json")).findings
               if f.id == "seq_scan_hot")
    assert seq.severity == "high"
    assert seq.suggestion


def test_fast_query_seq_scan_not_flagged():
    # 80% of the time, but only 4 ms total: not worth flagging.
    fast = [{"Plan": {
        "Node Type": "Seq Scan", "Relation Name": "small",
        "Plan Rows": 100, "Plan Width": 8, "Actual Startup Time": 0.0,
        "Actual Total Time": 4.0, "Actual Rows": 100, "Actual Loops": 1},
        "Execution Time": 5.0}]
    report = dataxplan.analyze(fast)
    assert "seq_scan_hot" not in {f.id for f in report.findings}
    assert report.ok
