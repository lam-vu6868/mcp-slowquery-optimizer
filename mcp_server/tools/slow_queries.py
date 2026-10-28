"""
mcp_server/tools/slow_queries.py
--------------------------------

CHỨC NĂNG :
    TOOL 1 — get_slow_queries: trả top N query chậm (digest, latency, rows examined).

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Nguồn chính: performance_schema.events_statements_summary_by_digest; phụ: mysql.slow_log.
    - Strip comment khỏi SQL trước khi trả (chống injection qua slow log) và gắn untrusted=true.
    - Tối đa 100 dòng, có cờ truncated.
    - Dùng readonly_user.

THAM KHẢO  : docs/api-contract.md (Tool 1)
"""

import json
import math
import time
from datetime import UTC, datetime

import pymysql

from mcp_server.utils.config import Config
from mcp_server.utils.db import get_conn
from mcp_server.utils.logger import get_logger
from mcp_server.utils.sanitize import strip_sql_comments

logger = get_logger(__name__)
ORDER_COLUMNS = {
    "total_latency": "SUM_TIMER_WAIT",
    "avg_latency": "AVG_TIMER_WAIT",
    "p95_latency": "QUANTILE_95",
    "exec_count": "COUNT_STAR",
}


async def get_slow_queries(
    limit: int = 10,
    min_avg_latency_ms: float = 500,
    order_by: str = "total_latency",
    since: str | None = None,
) -> str:
    """Trả top digest chậm; thời gian và P95 là số liệu tích lũy của MySQL."""
    started = time.perf_counter()

    def response(data=None, error=None, truncated=False):
        return json.dumps({
            "ok": error is None,
            "data": data,
            "error": error,
            "meta": {
                "tool": "get_slow_queries",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "truncated": truncated,
            },
        }, ensure_ascii=False)

    if type(limit) is not int or not 1 <= limit <= 100:
        return response(error={"code": "INVALID_INPUT", "message": "limit phải từ 1 đến 100", "detail": {}})
    if type(min_avg_latency_ms) not in (int, float) or not math.isfinite(min_avg_latency_ms) or min_avg_latency_ms < 0:
        return response(error={"code": "INVALID_INPUT", "message": "min_avg_latency_ms phải là số không âm", "detail": {}})
    if type(order_by) is not str or order_by not in ORDER_COLUMNS:
        return response(error={"code": "INVALID_INPUT", "message": "order_by không hợp lệ", "detail": {}})

    since_dt = None
    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                raise ValueError("timezone required")
            since_dt = since_dt.astimezone(UTC).replace(tzinfo=None)
        except (AttributeError, TypeError, ValueError):
            return response(error={"code": "INVALID_INPUT", "message": "since phải là ISO 8601 có múi giờ", "detail": {}})

    sql = """
        SELECT DIGEST, COALESCE(NULLIF(QUERY_SAMPLE_TEXT, ''), DIGEST_TEXT) AS sql_text,
               COUNT_STAR, AVG_TIMER_WAIT, QUANTILE_95, SUM_TIMER_WAIT,
               SUM_ROWS_EXAMINED, SUM_ROWS_SENT, FIRST_SEEN, LAST_SEEN
        FROM performance_schema.events_statements_summary_by_digest
        WHERE SCHEMA_NAME = %s AND DIGEST IS NOT NULL AND COUNT_STAR > 0
          AND (DIGEST_TEXT LIKE 'SELECT%%' OR DIGEST_TEXT LIKE 'WITH%%')
          AND AVG_TIMER_WAIT >= %s
    """
    params = [Config.DB_NAME, min_avg_latency_ms * 1_000_000_000]
    if since_dt is not None:
        # shortcut: LAST_SEEN filters active digests; metrics still cover their full lifetime.
        sql += " AND LAST_SEEN >= %s"
        params.append(since_dt)
    sql += f" ORDER BY {ORDER_COLUMNS[order_by]} DESC, DIGEST ASC LIMIT %s"
    params.append(limit + 1)

    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SET time_zone = '+00:00'")
            cur.execute(sql, params)
            rows = cur.fetchall()
    except pymysql.MySQLError as exc:
        logger.error("get_slow_queries failed: %s", type(exc).__name__)
        return response(error={"code": "INTERNAL", "message": "Không đọc được thống kê slow query", "detail": {}})

    queries = []
    for row in rows[:limit]:
        count = row["COUNT_STAR"]
        queries.append({
            "query_id": row["DIGEST"],
            "digest": row["DIGEST"],
            "sql_text": strip_sql_comments(row["sql_text"] or ""),
            "untrusted": True,
            "exec_count": count,
            "avg_latency_ms": round(row["AVG_TIMER_WAIT"] / 1_000_000_000, 2),
            "p95_latency_ms": round(row["QUANTILE_95"] / 1_000_000_000, 2) if row["QUANTILE_95"] is not None else None,
            "total_latency_ms": round(row["SUM_TIMER_WAIT"] / 1_000_000_000, 2),
            "rows_examined_avg": round(row["SUM_ROWS_EXAMINED"] / count, 2),
            "rows_sent_avg": round(row["SUM_ROWS_SENT"] / count, 2),
            "first_seen": row["FIRST_SEEN"].isoformat().removesuffix("+00:00") + "Z",
            "last_seen": row["LAST_SEEN"].isoformat().removesuffix("+00:00") + "Z",
        })

    return response(data={"queries": queries}, truncated=len(rows) > limit)
