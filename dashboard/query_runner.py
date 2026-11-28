"""
dashboard/query_runner.py
-------------------------

CHỨC NĂNG : Chạy 1 lượt câu SELECT bằng readonly_user và đo thời gian thực tế (ms),
            số dòng kết quả, số dòng phải quét. Dùng cho trang "Chọn query chậm".
PHỤ TRÁCH  : Vũ · Tình    |    REVIEW: Hải
LƯU Ý      : Mọi SQL phải qua AST whitelist; đặt MAX_EXECUTION_TIME; đọc kết quả theo lô
             và chỉ giữ tối đa 20 dòng để hiển thị (không giữ toàn bộ trong RAM).
"""

import time

import pymysql.cursors

from mcp_server.utils.db import get_conn
from security.ast_whitelist import check as ast_check

MAX_PREVIEW_ROWS = 20
TIMEOUT_MS = 30000
SLOW_THRESHOLD_MS = 500.0


def _handler_reads(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SHOW SESSION STATUS LIKE 'Handler_read%'")
        rows = cur.fetchall()
    total = 0
    for row in rows:
        if isinstance(row, dict):
            val = row.get("Value") or row.get("value") or 0
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            val = row[1]
        else:
            val = 0
        try:
            total += int(val)
        except (TypeError, ValueError):
            pass
    return total


def run_query_once(sql: str, *, conn_factory=get_conn, timeout_ms: int = TIMEOUT_MS) -> dict:
    """Chạy 1 lượt SELECT, trả latency_ms, row_count, rows_examined và mẫu kết quả."""
    ok, reason = ast_check(sql)
    if not ok:
        raise ValueError(f"SQL bị AST whitelist từ chối: {reason}")

    with conn_factory() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {int(timeout_ms)}")
        reads_before = _handler_reads(conn)
        t0 = time.perf_counter()
        preview: list[dict] = []
        row_count = 0
        with conn.cursor(pymysql.cursors.SSDictCursor) as stream_cur:
            stream_cur.execute(sql)
            while True:
                batch = stream_cur.fetchmany(1000)
                if not batch:
                    break
                if len(preview) < MAX_PREVIEW_ROWS:
                    need = MAX_PREVIEW_ROWS - len(preview)
                    preview.extend(
                        {str(k): str(v) for k, v in row.items()} for row in batch[:need]
                    )
                row_count += len(batch)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        reads_after = _handler_reads(conn)

    return {
        "latency_ms": elapsed_ms,
        "row_count": row_count,
        "rows_examined": max(0, reads_after - reads_before),
        "preview": preview,
        "exceeded_slow_threshold": elapsed_ms >= SLOW_THRESHOLD_MS,
    }
