import pytest

from chunker.export import postgres_spec_exporter as exporter


def test_sql_file_escapes_every_interpolated_string(tmp_path, monkeypatch):
    injection = "value'; DROP TABLE nodes; --"
    monkeypatch.setattr(exporter, "_collect_chunks", lambda _: [object()])
    monkeypatch.setattr(
        exporter,
        "_rows_for_nodes_edges_spans",
        lambda _: (
            [
                {
                    "id": injection,
                    "file": injection,
                    "lang": injection,
                    "symbol": injection,
                    "kind": injection,
                    "attrs": {"value": injection},
                },
            ],
            [{"src": injection, "dst": injection, "type": injection, "weight": 1}],
            [[injection, injection, 0, 1]],
        ),
    )

    exporter.export(str(tmp_path))

    sql = (tmp_path / "chunker_export.sql").read_text(encoding="utf-8")
    assert "value''; DROP TABLE nodes; --" in sql


def test_direct_export_rejects_unapproved_dsn_host(tmp_path):
    with pytest.raises(ValueError, match="not approved"):
        exporter.export(
            str(tmp_path),
            {"dsn": "postgresql://user:password@unapproved.example/database"},
        )
