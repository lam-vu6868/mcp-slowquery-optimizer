"""
mcp_server/tools/benchmark.py
-----------------------------
CHỨC NĂNG:
    TOOL 5 — benchmark_query: đo P50/P95 latency, rows examined
    và hash kết quả truy vấn.

PHỤ TRÁCH:
    Hải tiếp quản phần sửa và đo P95 từ Tường.
    REVIEW: Tường hoặc Vũ.

CÁCH ĐO:
    - Warm-up mặc định 3 lần và bỏ kết quả warm-up.
    - Đo mặc định 20 lần; P95 tính theo phương pháp nearest-rank.
    - Thời gian đo bao gồm thời gian MySQL xử lý và truyền hết kết quả.
    - Đọc kết quả theo từng lô bằng SSDictCursor, không dùng fetchall()
      cho dữ liệu truy vấn nên không giữ toàn bộ kết quả trong RAM.
    - rows_examined được tính bằng chênh lệch Handler_read* trước/sau
      từng lượt; kết quả trả về là trung vị của các lượt đo thành công.
    - Hash chạy trong một lượt riêng, không tính vào P50/P95.
    - Query không có ORDER BY được ghi vào SQLite tạm, sắp xếp trên
      ổ đĩa rồi mới hash; deterministic_order=false.

AN TOÀN VÀ GIỚI HẠN:
    - Mọi SQL phải qua AST whitelist trước khi chạy.
    - Chỉ dùng readonly_user và đặt MAX_EXECUTION_TIME cho session.
    - measured_runs chỉ nhận 5-50; timeout_ms tối đa 60000 ms.
    - Không dùng FLUSH STATUS vì readonly_user không có quyền RELOAD.
    - Kết quả thiếu lượt đo hoặc có timeout không được dùng làm
      baseline chính thức.

THAM KHẢO:
    - docs/api-contract.md (Tool 5)
    - project-management/ROADMAP.md (mục 2.3)
"""
import sys
import os

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import hashlib
import json
import math
import sqlite3
import statistics
import tempfile
import time
from datetime import date, datetime
from decimal import Decimal

import pymysql

from mcp_server.utils.db import get_conn
from mcp_server.utils.logger import get_logger
from security.ast_whitelist import check as ast_check


logger = get_logger(__name__)
BATCH_SIZE = 1000


def _normalise_value(value):
    """Chuyen gia tri DB sang dang JSON on dinh de hash."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    return value


def _canonical_row(row) -> str:
    """Bieu dien mot dong theo thu tu cot on dinh."""
    if isinstance(row, dict):
        payload = {
            str(key): _normalise_value(row[key])
            for key in sorted(row.keys(), key=str)
        }
    elif isinstance(row, (list, tuple)):
        payload = [_normalise_value(value) for value in row]
    else:
        payload = _normalise_value(row)

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _drain_stream(cur, batch_size: int = BATCH_SIZE) -> int:
    """Doc va bo ket qua theo lo; tra ve tong so dong."""
    row_count = 0
    while True:
        batch = cur.fetchmany(batch_size)
        if not batch:
            break
        row_count += len(batch)
    return row_count


def _get_handler_reads(conn) -> int:
    """Lay tong cac bo dem Handler_read* cua session hien tai."""
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW SESSION STATUS LIKE 'Handler_read%'")
            rows = cur.fetchall()

        total = 0
        for row in rows:
            if isinstance(row, dict):
                value = row.get("Value") or row.get("value") or 0
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                value = row[1]
            else:
                value = 0
            total += int(value)
        return total
    except Exception as exc:
        logger.warning(f"Khong do duoc Handler_read*: {str(exc)[:80]}")
        return 0


def _run_streamed_once(conn, sql: str) -> tuple[float, int, int]:
    """Chay mot luot, stream het ket qua va tra latency/rows read/row count."""
    before_reads = _get_handler_reads(conn)
    started = time.perf_counter()

    with conn.cursor(pymysql.cursors.SSDictCursor) as cur:
        cur.execute(sql)
        row_count = _drain_stream(cur)

    latency_ms = (time.perf_counter() - started) * 1000
    after_reads = _get_handler_reads(conn)
    rows_examined = max(0, after_reads - before_reads)
    return latency_ms, rows_examined, row_count


def _hash_streamed_result(
    conn,
    sql: str,
    has_order_by: bool,
) -> tuple[str, int]:
    """
    Hash ket qua trong mot luot rieng.

    Co ORDER BY: hash truc tiep theo thu tu query.
    Khong ORDER BY: ghi tung dong vao SQLite tam, sap xep tren dia roi hash.
    """
    digest = hashlib.sha256()
    row_count = 0

    if has_order_by:
        with conn.cursor(pymysql.cursors.SSDictCursor) as cur:
            cur.execute(sql)
            while True:
                batch = cur.fetchmany(BATCH_SIZE)
                if not batch:
                    break
                for row in batch:
                    digest.update(_canonical_row(row).encode("utf-8"))
                    digest.update(b"\n")
                    row_count += 1
        if row_count == 0:
            digest.update(b"EMPTY")
        return "sha256:" + digest.hexdigest(), row_count

    temp_fd, temp_path = tempfile.mkstemp(
        prefix="mcp_benchmark_hash_",
        suffix=".sqlite3",
    )
    os.close(temp_fd)
    temp_db = None

    try:
        temp_db = sqlite3.connect(temp_path)
        temp_db.execute("PRAGMA journal_mode=OFF")
        temp_db.execute("PRAGMA synchronous=OFF")
        temp_db.execute("PRAGMA temp_store=FILE")
        temp_db.execute("CREATE TABLE result_rows (row_text TEXT NOT NULL)")

        with conn.cursor(pymysql.cursors.SSDictCursor) as cur:
            cur.execute(sql)
            while True:
                batch = cur.fetchmany(BATCH_SIZE)
                if not batch:
                    break
                canonical_batch = [(_canonical_row(row),) for row in batch]
                temp_db.executemany(
                    "INSERT INTO result_rows(row_text) VALUES (?)",
                    canonical_batch,
                )
                row_count += len(canonical_batch)

        temp_db.commit()
        for (row_text,) in temp_db.execute(
            "SELECT row_text FROM result_rows ORDER BY row_text"
        ):
            digest.update(row_text.encode("utf-8"))
            digest.update(b"\n")

        if row_count == 0:
            digest.update(b"EMPTY")
        return "sha256:" + digest.hexdigest(), row_count
    finally:
        if temp_db is not None:
            temp_db.close()
        try:
            os.remove(temp_path)
        except OSError:
            pass


def _is_timeout(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "maximum statement execution time" in message
        or "query execution was interrupted" in message
        or "max_execution_time" in message
    )


def _error_response(code: str, message: str, t_start: float) -> str:
    return json.dumps({
        "ok": False,
        "data": None,
        "error": {"code": code, "message": message, "detail": {}},
        "meta": {
            "tool": "benchmark_query",
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 2),
            "truncated": False,
        },
    }, ensure_ascii=False)


async def benchmark_query(
    sql: str,
    warmup_runs: int = 3,
    measured_runs: int = 20,
    timeout_ms: int = 30000,
    use_invisible_indexes: bool = False,
    compute_result_hash: bool = True,
) -> str:
    """Do P50/P95 voi ket qua duoc doc theo lo."""
    t_start = time.perf_counter()

    if not sql or not sql.strip():
        return _error_response("INVALID_INPUT", "sql rong", t_start)
    if not isinstance(warmup_runs, int) or warmup_runs < 0:
        return _error_response(
            "INVALID_INPUT", "warmup_runs phai la so nguyen >= 0", t_start
        )
    if not isinstance(measured_runs, int) or not (5 <= measured_runs <= 50):
        return _error_response(
            "INVALID_INPUT", "measured_runs phai trong khoang 5-50", t_start
        )
    if not isinstance(timeout_ms, int) or not (1000 <= timeout_ms <= 60000):
        return _error_response(
            "INVALID_INPUT", "timeout_ms phai trong khoang 1000-60000", t_start
        )

    ast_result = ast_check(sql)
    if isinstance(ast_result, tuple) and len(ast_result) == 2:
        ok, reason = ast_result
    elif isinstance(ast_result, dict):
        ok = ast_result.get("ok", False)
        reason = ast_result.get("rule") or ast_result.get(
            "reason", "AST rejected"
        )
    else:
        ok, reason = False, "AST check tra ve format khong hop le"

    if not ok:
        logger.warning(f"[benchmark_query] AST_REJECTED: {reason}")
        return _error_response("AST_REJECTED", reason, t_start)

    has_order_by = "ORDER BY" in sql.upper()
    latencies = []
    rows_examined_samples = []
    timed_out_runs = 0
    last_row_count = 0

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {timeout_ms}")
                if use_invisible_indexes:
                    cur.execute(
                        "SET SESSION optimizer_switch = "
                        "'use_invisible_indexes=on'"
                    )

            for _ in range(warmup_runs):
                try:
                    _run_streamed_once(conn, sql)
                except Exception as exc:
                    if _is_timeout(exc):
                        return _error_response(
                            "TIMEOUT",
                            f"Warm-up timeout (>{timeout_ms}ms)",
                            t_start,
                        )
                    raise

            for _ in range(measured_runs):
                try:
                    latency_ms, rows_examined, row_count = _run_streamed_once(
                        conn, sql
                    )
                    latencies.append(latency_ms)
                    rows_examined_samples.append(rows_examined)
                    last_row_count = row_count
                except Exception as exc:
                    if _is_timeout(exc):
                        timed_out_runs += 1
                        continue
                    raise

            if not latencies:
                return _error_response(
                    "TIMEOUT",
                    f"Tat ca {measured_runs} lan do deu timeout "
                    f"(>{timeout_ms}ms)",
                    t_start,
                )

            result_hash = None
            row_count = last_row_count
            if compute_result_hash:
                result_hash, row_count = _hash_streamed_result(
                    conn,
                    sql,
                    has_order_by,
                )

    except Exception as exc:
        logger.error(f"[benchmark_query] ERROR: {str(exc)[:200]}")
        if _is_timeout(exc):
            return _error_response("TIMEOUT", str(exc)[:200], t_start)
        return _error_response("INTERNAL", str(exc)[:200], t_start)

    latencies_sorted = sorted(latencies)
    n = len(latencies_sorted)
    p50 = statistics.median(latencies_sorted)
    p95_index = max(0, math.ceil(n * 0.95) - 1)
    p95 = latencies_sorted[p95_index]
    min_ms = latencies_sorted[0]
    max_ms = latencies_sorted[-1]
    stddev = statistics.pstdev(latencies_sorted) if n > 1 else 0.0
    rows_examined = int(statistics.median(rows_examined_samples))

    duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
    logger.info(
        f"[benchmark_query] {n} runs OK | p50={round(p50, 2)}ms | "
        f"p95={round(p95, 2)}ms | timeouts={timed_out_runs} | "
        f"rows_examined={rows_examined}"
    )

    data = {
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "min_ms": round(min_ms, 2),
        "max_ms": round(max_ms, 2),
        "stddev_ms": round(stddev, 2),
        "runs": n,
        "timed_out_runs": timed_out_runs,
        "rows_examined": rows_examined,
        "cache_state": "warm",
        "result_hash": result_hash,
        "row_count": row_count,
        "deterministic_order": has_order_by,
    }

    warnings = []
    if not has_order_by:
        warnings.append(
            "Query khong co ORDER BY - da sap xep tren dia truoc khi hash"
        )
    if n != measured_runs:
        warnings.append(
            f"Chi co {n}/{measured_runs} lan do thanh cong; "
            "khong dung ket qua nay lam baseline chinh thuc"
        )
    if warnings:
        data["warnings"] = warnings

    return json.dumps({
        "ok": True,
        "data": data,
        "error": None,
        "meta": {
            "tool": "benchmark_query",
            "duration_ms": duration_ms,
            "truncated": False,
        },
    }, ensure_ascii=False, default=str)


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        cases = [
            (
                "Query cham (case study) - 5 runs",
                "SELECT SUM(total_revenue) FROM sales_data "
                "WHERE region = 'Asia' AND order_date >= '2024-01-01'",
                {"warmup_runs": 1, "measured_runs": 5, "timeout_ms": 30000},
                True,
            ),
            (
                "Query nhanh - 5 runs",
                "SELECT * FROM sales_data WHERE region = 'Asia' LIMIT 100",
                {"warmup_runs": 1, "measured_runs": 5, "timeout_ms": 30000},
                True,
            ),
            ("DROP TABLE -> chan", "DROP TABLE sales_data", {"measured_runs": 5}, False),
            ("measured_runs < 5 -> chan", "SELECT 1", {"measured_runs": 2}, False),
            ("measured_runs > 50 -> chan", "SELECT 1", {"measured_runs": 100}, False),
            ("timeout_ms > 60000 -> chan", "SELECT 1", {"timeout_ms": 70000}, False),
            ("SQL rong -> chan", "", {}, False),
        ]

        print("=" * 80)
        print("TEST TOOL 5 - BENCHMARK_QUERY (STREAMING)")
        print("=" * 80)
        passed = 0

        for label, sql, kwargs, expect_ok in cases:
            print(f"\n[{label}]")
            result = json.loads(await benchmark_query(sql, **kwargs))
            case_ok = result["ok"] == expect_ok
            if result["ok"]:
                data = result["data"]
                case_ok = case_ok and data["runs"] == kwargs.get(
                    "measured_runs", 20
                )
                case_ok = case_ok and data["timed_out_runs"] == 0
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(result["error"])

            passed += int(case_ok)
            print("PASS" if case_ok else "FAIL")

        print("=" * 80)
        print(f"KET QUA: {passed}/{len(cases)} pass")
        print("=" * 80)

    asyncio.run(run_tests())
