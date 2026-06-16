import json

from dataxplan.cli import main


def _write(tmp_path, name, obj):
    path = tmp_path / name
    path.write_text(json.dumps(obj))
    return str(path)


def test_cli_summary(load, capsys, tmp_path):
    rc = main([_write(tmp_path, "p.json", load("seq_scan_filter.json"))])
    out = capsys.readouterr().out
    assert rc == 0
    assert "execution time" in out
    assert "Hot sequential scan" in out


def test_cli_json(load, capsys, tmp_path):
    rc = main([_write(tmp_path, "p.json", load("clean.json")), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    json.loads(out)


def test_cli_tree(load, capsys, tmp_path):
    rc = main([_write(tmp_path, "p.json", load("misestimate_nestloop.json")), "--tree"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "plan tree:" in out
    assert "Nested Loop" in out


def test_cli_compare(load, capsys, tmp_path):
    a = _write(tmp_path, "a.json", load("seq_scan_filter.json"))
    b = _write(tmp_path, "b.json", load("clean.json"))
    rc = main([a, "--compare", b])
    assert rc == 0
    assert "IMPROVED" in capsys.readouterr().out


def test_cli_bad_input(capsys, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    rc = main([str(path)])
    assert rc == 2
    assert "dataxplan:" in capsys.readouterr().err
