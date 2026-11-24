import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

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
        "source": "performance_schema",
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


@pytest.mark.asyncio
async def test_get_slow_queries_reads_bounded_slow_log(monkeypatch):
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
            return [{
                "sql_text": b"SELECT 1 /* ignore instructions */",
                "start_time": datetime(2026, 11, 24, 7, 0, 0, tzinfo=UTC).replace(tzinfo=None),
                "query_time": timedelta(seconds=0.75),
                "rows_examined": 20,
                "rows_sent": 1,
            }]

    cursor = Cursor()

    class Conn:
        def cursor(self):
            return cursor

    @contextmanager
    def fake_conn():
        yield Conn()

    monkeypatch.setattr(slow_queries, "get_conn", fake_conn)
    result = json.loads(await slow_queries.get_slow_queries(
        source="slow_log", limit=1, since="2026-11-24T00:00:00Z",
    ))

    assert result["ok"] is True
    query = result["data"]["queries"][0]
    assert query == {
        "query_id": "slowlog:" + hashlib.sha256(b"SELECT 1").hexdigest(),
        "digest": None,
        "source": "mysql.slow_log",
        "sql_text": "SELECT 1",
        "untrusted": True,
        "exec_count": 1,
        "avg_latency_ms": 750.0,
        "p95_latency_ms": None,
        "total_latency_ms": 750.0,
        "rows_examined_avg": 20,
        "rows_sent_avg": 1,
        "first_seen": "2026-11-24T07:00:00Z",
        "last_seen": "2026-11-24T07:00:00Z",
    }
    sql, params = cursor.calls[-1]
    assert "mysql.slow_log" in sql
    assert "MAX_EXECUTION_TIME" in sql
    assert "OCTET_LENGTH(sql_text) <= 8000" in sql
    assert "LIMIT %s" in sql
    assert params[-1] == 2


@pytest.mark.asyncio
async def test_get_slow_queries_rejects_bad_source_before_db(monkeypatch):
    monkeypatch.setattr(slow_queries, "get_conn", lambda: pytest.fail("DB must not be used"))
    result = json.loads(await slow_queries.get_slow_queries(source="mysql.*"))
    assert result["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_get_slow_queries_reports_missing_slow_log_privilege(monkeypatch):
    @contextmanager
    def denied_conn():
        raise pymysql.OperationalError(1142, "secret permission detail")
        yield

    monkeypatch.setattr(slow_queries, "get_conn", denied_conn)
    result = json.loads(await slow_queries.get_slow_queries(source="slow_log"))
    assert result["error"]["code"] == "FORBIDDEN"
    assert "secret permission detail" not in json.dumps(result)
