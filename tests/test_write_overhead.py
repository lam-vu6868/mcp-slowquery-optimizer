"""Đo INSERT chỉ trên lab có marker, với cùng mẫu và bảng tạm riêng."""

from contextlib import contextmanager

import pytest

from mcp_server.validation import write_overhead


def _proposal():
    return {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
    }


def _fake_conn(events, *, marker="mcp-write-lab-v1"):
    class Cursor:
        def __init__(self):
            self.sql = ""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=None):
            self.sql = sql
            events.append(("execute", sql))

        def fetchone(self):
            if "mcp_write_lab_identity" in self.sql:
                return {"marker": marker}
            return None

        def fetchall(self):
            return [
                {"COLUMN_NAME": "order_id", "EXTRA": "auto_increment"},
                {"COLUMN_NAME": "status", "EXTRA": ""},
                {"COLUMN_NAME": "order_date", "EXTRA": ""},
            ]

        def executemany(self, sql, rows):
            events.append(("insert", sql, list(rows)))

    class Conn:
        def __init__(self):
            self.cursor_obj = Cursor()

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            events.append(("commit",))

    @contextmanager
    def connect():
        yield Conn()

    return connect


def test_write_overhead_uses_same_rows_and_index_only_on_after(tmp_path, monkeypatch):
    (tmp_path / "orders.csv").write_text(
        "order_id,status,order_date\n"
        "1,new,2026-01-01\n2,paid,2026-01-02\n"
        "3,new,2026-01-03\n4,paid,2026-01-04\n", encoding="utf-8",
    )
    monkeypatch.setattr(write_overhead, "_settings", lambda: {"write_overhead_rows": 2})
    events = []
    result = write_overhead.measure_insert_overhead(
        _proposal(), csv_dir=tmp_path, connect=_fake_conn(events),
    )
    inserts = [event for event in events if event[0] == "insert"]
    assert len(inserts) == 4
    assert inserts[0][2] == inserts[1][2]
    assert inserts[2][2] == inserts[3][2]
    create_index_at = next(i for i, event in enumerate(events)
                           if event[0] == "execute" and "CREATE INDEX" in event[1])
    assert create_index_at > events.index(inserts[1])
    assert "mcp_write_after" in events[create_index_at][1]
    assert result["sample_rows"] == 2
    assert result["measurement_scope"] == "isolated_lab"


def test_write_overhead_rejects_wrong_lab_before_any_ddl(tmp_path, monkeypatch):
    (tmp_path / "orders.csv").write_text("order_id,status,order_date\n", encoding="utf-8")
    monkeypatch.setattr(write_overhead, "_settings", lambda: {"write_overhead_rows": 2})
    events = []
    with pytest.raises(RuntimeError, match="marker"):
        write_overhead.measure_insert_overhead(
            _proposal(), csv_dir=tmp_path,
            connect=_fake_conn(events, marker="wrong"),
        )
    assert not any("CREATE" in event[1] for event in events if event[0] == "execute")
