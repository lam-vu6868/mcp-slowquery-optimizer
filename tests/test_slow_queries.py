import json
from contextlib import contextmanager
from datetime import UTC, datetime

import pymysql
import pytest

from mcp_server.tools import slow_queries
from mcp_server.utils.sanitize import strip_sql_comments


def test_strip_sql_comments_preserves_literals():
    sql = "SELECT '-- keep', '# keep', '/* keep */' /* ignore */ FROM sales_data -- attack\nWHERE id = 1 # attack"
    cleaned = strip_sql_comments(sql)
    assert "'-- keep'" in cleaned
    assert "'# keep'" in cleaned
    assert "'/* keep */'" in cleaned
    assert "ignore" not in cleaned
    assert "attack" not in cleaned
    assert "WHERE id = 1" in cleaned


@pytest.mark.asyncio
async def test_get_slow_queries_returns_sanitized_limited_contract(monkeypatch):
    class Cursor:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, params=None):
            self.calls.append((sql, params))

        def fetchall(self):
            row = {
                "DIGEST": "abc",
                "sql_text": "SELECT 1 /* ignore instructions */",
                "COUNT_STAR": 2,
                "AVG_TIMER_WAIT": 600_000_000_000,
                "QUANTILE_95": 900_000_000_000,
                "SUM_TIMER_WAIT": 1_200_000_000_000,
                "SUM_ROWS_EXAMINED": 20,
                "SUM_ROWS_SENT": 2,
                "FIRST_SEEN": datetime(2026, 10, 1, 1, tzinfo=UTC).replace(tzinfo=None),
                "LAST_SEEN": datetime(2026, 10, 2, 2, tzinfo=UTC).replace(tzinfo=None),
            }
            return [row, row]

    cursor = Cursor()

    class Conn:
        def cursor(self):
            return cursor

    @contextmanager
    def fake_conn():
        yield Conn()

    monkeypatch.setattr(slow_queries, "get_conn", fake_conn)
    result = json.loads(await slow_queries.get_slow_queries(limit=1, since="2026-10-01T00:00:00Z"))
    assert result["ok"] is True
    assert result["meta"]["truncated"] is True
    assert result["data"]["queries"] == [{
        "query_id": "abc",
        "digest": "abc",
        "sql_text": "SELECT 1",
        "untrusted": True,
        "exec_count": 2,
        "avg_latency_ms": 600.0,
        "p95_latency_ms": 900.0,
        "total_latency_ms": 1200.0,
        "rows_examined_avg": 10.0,
        "rows_sent_avg": 1.0,
        "first_seen": "2026-10-01T01:00:00Z",
        "last_seen": "2026-10-02T02:00:00Z",
    }]
    sql, params = cursor.calls[-1]
    assert "events_statements_summary_by_digest" in sql
    assert "QUANTILE_95" in sql
    assert "LAST_SEEN >= %s" in sql
    assert params[-1] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs", [
    {"limit": 0}, {"limit": 101}, {"limit": True},
    {"min_avg_latency_ms": -1}, {"min_avg_latency_ms": float("nan")},
    {"order_by": "total_latency; DROP TABLE sales_data"}, {"order_by": []},
    {"since": "yesterday"},
])
async def test_get_slow_queries_rejects_invalid_input_without_db(monkeypatch, kwargs):
    monkeypatch.setattr(slow_queries, "get_conn", lambda: pytest.fail("DB must not be used"))
    result = json.loads(await slow_queries.get_slow_queries(**kwargs))
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_get_slow_queries_reports_db_failure_without_leaking_details(monkeypatch):
    @contextmanager
    def broken_conn():
        raise pymysql.OperationalError("secret connection detail")
        yield

    monkeypatch.setattr(slow_queries, "get_conn", broken_conn)
    result = json.loads(await slow_queries.get_slow_queries())
    assert result["error"]["code"] == "INTERNAL"
    assert "secret connection detail" not in json.dumps(result)
