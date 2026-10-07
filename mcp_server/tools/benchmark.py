"""
mcp_server/tools/benchmark.py
-----------------------------
CHỨC NĂNG:
    TOOL 5 — benchmark_query: đo P50/P95 latency và hash kết quả.

PHỤ TRÁCH: Tường    |    REVIEW: Hải

LƯU Ý:
    - Mọi SQL phải qua AST whitelist TRƯỚC khi chạy.
    - Warm-up N lần (bỏ), đo M lần (5-50), ghi rõ cache_state.
    - Timeout mỗi lần chạy (≤ 60000ms).
    - Query không có ORDER BY xác định → sort trước khi hash
      và đặt deterministic_order=false.
    - Dùng readonly_user + MAX_EXECUTION_TIME.
    - KHÔNG dùng FLUSH STATUS (readonly_user không có quyền RELOAD).

THAM KHẢO:
    - docs/api-contract.md (Tool 5)
    - project-management/ROADMAP.md (mục 2.3)
"""
import sys
import os

# Fix import path khi chạy file trực tiếp
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import json
import time
import hashlib
import statistics
from mcp_server.utils.db import get_conn
from mcp_server.utils.logger import get_logger
from mcp_server.utils.config import Config
from security.ast_whitelist import check as ast_check

logger = get_logger(__name__)


# ============================================================
# HASH KẾT QUẢ
# ============================================================

def _hash_rows(rows) -> str:
    """
    Hash kết quả query.
    Sort trước khi hash để đảm bảo ổn định với query không có ORDER BY.
    """
    if not rows:
        return "sha256:" + hashlib.sha256(b"EMPTY").hexdigest()

    str_rows = [str(dict(r)) if isinstance(r, dict) else str(r) for r in rows]
    str_rows.sort()

    h = hashlib.sha256()
    for r in str_rows:
        h.update(r.encode("utf-8"))
        h.update(b"\n")
    return "sha256:" + h.hexdigest()


# ============================================================
# ĐO rows_examined — AN TOÀN
# ============================================================

def _get_rows_examined(cur) -> int:
    """
    Đo rows_examined từ session status.
    Dùng Handler_read_rnd_next — metric chính xác nhất cho full scan.

    Returns:
        int — số dòng đã đọc, hoặc 0 nếu không đo được.
    """
    try:
        cur.execute("SHOW SESSION STATUS LIKE 'Handler_read_rnd_next'")
        row = cur.fetchone()
        if row is None:
            return 0

        # Trường hợp 1: DictCursor → {'Variable_name': ..., 'Value': '...'}
        if isinstance(row, dict):
            value = row.get("Value") or row.get("value")
            if value is not None:
                return int(value)

        # Trường hợp 2: TupleCursor → ('Handler_read_rnd_next', '123')
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            return int(row[1])

        # Trường hợp 3: không rõ → trả 0
        return 0

    except Exception as e:
        logger.warning(f"Không đo được rows_examined: {str(e)[:80]}")
        return 0


# ============================================================
# ERROR HELPER
# ============================================================

def _error_response(code: str, message: str, t_start: float) -> str:
    """Trả JSON lỗi theo contract"""
    return json.dumps({
        "ok": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "detail": {},
        },
        "meta": {
            "tool": "benchmark_query",
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 2),
            "truncated": False,
        },
    }, ensure_ascii=False)


# ============================================================
# MAIN TOOL FUNCTION
# ============================================================

async def benchmark_query(
    sql: str,
    warmup_runs: int = 3,
    measured_runs: int = 20,
    timeout_ms: int = 30000,
    use_invisible_indexes: bool = False,
    compute_result_hash: bool = True,
) -> str:
    """
    Đo P50/P95 latency của query.

    Args:
        sql: Câu SQL cần đo (chỉ SELECT)
        warmup_runs: Số lần warm-up (bỏ kết quả)
        measured_runs: Số lần đo thật (5-50)
        timeout_ms: Timeout mỗi lần chạy (1000-60000)
        use_invisible_indexes: Cho Validation Layer (LLM KHÔNG được đặt true)
        compute_result_hash: Có hash kết quả không

    Returns:
        JSON string theo contract api-contract.md mục Tool 5
    """
    t_start = time.perf_counter()

    # ------------------------------------------------
    # BƯỚC 1: Validate input
    # ------------------------------------------------
    if not sql or not sql.strip():
        return _error_response("INVALID_INPUT", "sql rỗng", t_start)

    if not isinstance(warmup_runs, int) or warmup_runs < 0:
        return _error_response(
            "INVALID_INPUT", "warmup_runs phải là số nguyên ≥ 0", t_start
        )

    if not isinstance(measured_runs, int) or not (5 <= measured_runs <= 50):
        return _error_response(
            "INVALID_INPUT", "measured_runs phải trong khoảng 5-50", t_start
        )

    if not isinstance(timeout_ms, int) or not (1000 <= timeout_ms <= 60000):
        return _error_response(
            "INVALID_INPUT", "timeout_ms phải trong khoảng 1000-60000", t_start
        )

    # ------------------------------------------------
    # BƯỚC 2: Check AST whitelist (fail-closed)
    # ------------------------------------------------
    ast_result = ast_check(sql)
    # ast_check trả về tuple (ok: bool, reason: str)
    if isinstance(ast_result, tuple) and len(ast_result) == 2:
        ok, reason = ast_result
    elif isinstance(ast_result, dict):
        # Fallback nếu ai đó đổi ast_whitelist trả về dict
        ok = ast_result.get("ok", False)
        reason = ast_result.get("rule") or ast_result.get("reason", "AST rejected")
    else:
        ok, reason = False, "AST check trả về format không hợp lệ"

    if not ok:
        logger.warning(f"[benchmark_query] AST_REJECTED: {reason}")
        return _error_response("AST_REJECTED", reason, t_start)

    # ------------------------------------------------
    # BƯỚC 3: Chuẩn bị chạy
    # ------------------------------------------------
    sql_upper = sql.upper()
    has_order_by = "ORDER BY" in sql_upper

    latencies = []
    timed_out_runs = 0
    rows_examined = 0
    last_rows = []
    error_msg = None

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                # Set timeout cho session
                cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {timeout_ms}")

                # Bật use_invisible_indexes (chỉ Validation Layer)
                if use_invisible_indexes:
                    cur.execute(
                        "SET SESSION optimizer_switch = 'use_invisible_indexes=on'"
                    )

                # ---- Warm-up (bỏ kết quả) ----
                for _ in range(warmup_runs):
                    try:
                        cur.execute(sql)
                        cur.fetchall()
                    except Exception as e:
                        if "maximum statement execution time" in str(e).lower():
                            timed_out_runs += 1
                        else:
                            raise

                # ---- Đo thật ----
                for i in range(measured_runs):
                    try:
                        t0 = time.perf_counter()
                        cur.execute(sql)
                        rows = cur.fetchall()
                        t1 = time.perf_counter()

                        latencies.append((t1 - t0) * 1000)

                        # Giữ kết quả lần cuối để hash
                        last_rows = rows

                    except Exception as e:
                        err_str = str(e).lower()
                        if "maximum statement execution time" in err_str:
                            timed_out_runs += 1
                            continue
                        error_msg = str(e)[:200]
                        break

                # ---- Đo rows_examined (an toàn, không lỗi) ----
                rows_examined = _get_rows_examined(cur)

    except Exception as e:
        logger.error(f"[benchmark_query] ERROR: {str(e)[:200]}")
        return _error_response("INTERNAL", str(e)[:200], t_start)

    # ------------------------------------------------
    # BƯỚC 4: Kiểm tra kết quả đo
    # ------------------------------------------------
    if error_msg:
        return _error_response("INTERNAL", error_msg, t_start)

    if not latencies:
        return _error_response(
            "TIMEOUT",
            f"Tất cả {measured_runs} lần chạy đều timeout (>{timeout_ms}ms)",
            t_start,
        )

    # ------------------------------------------------
    # BƯỚC 5: Tính P50/P95, min, max, stddev
    # ------------------------------------------------
    latencies_sorted = sorted(latencies)
    n = len(latencies_sorted)

    p50 = statistics.median(latencies_sorted)

    # P95: index ceil(n*0.95) - 1
    p95_index = max(0, int(round(n * 0.95)) - 1)
    p95 = latencies_sorted[p95_index]

    min_ms = latencies_sorted[0]
    max_ms = latencies_sorted[-1]
    stddev = statistics.pstdev(latencies_sorted) if n > 1 else 0.0

    # ------------------------------------------------
    # BƯỚC 6: Hash kết quả
    # ------------------------------------------------
    result_hash = None
    row_count = len(last_rows)

    if compute_result_hash:
        result_hash = _hash_rows(last_rows)

    # ------------------------------------------------
    # BƯỚC 7: Trả kết quả
    # ------------------------------------------------
    duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
    logger.info(
        f"[benchmark_query] {n} runs OK | p50={round(p50,2)}ms | "
        f"p95={round(p95,2)}ms | timeouts={timed_out_runs} | "
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

    # Cảnh báo nếu query không có ORDER BY
    warnings = []
    if not has_order_by:
        warnings.append("Query không có ORDER BY — đã sort trước khi hash")

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


# ============================================================
# TEST NHANH — CHẠY FILE TRỰC TIẾP
# ============================================================

if __name__ == "__main__":
    import asyncio

    async def run_tests():
        cases = [
            ("Query chậm (case study) — 5 runs",
             "SELECT SUM(total_revenue) FROM sales_data "
             "WHERE region = 'Asia' AND order_date >= '2024-01-01'",
             {"warmup_runs": 1, "measured_runs": 5, "timeout_ms": 30000},
             True),

            ("Query nhanh — 5 runs",
             "SELECT * FROM sales_data WHERE region = 'Asia' LIMIT 100",
             {"warmup_runs": 1, "measured_runs": 5, "timeout_ms": 30000},
             True),

            ("DROP TABLE → chặn",
             "DROP TABLE sales_data",
             {"measured_runs": 5},
             False),

            ("measured_runs < 5 → chặn",
             "SELECT 1",
             {"measured_runs": 2},
             False),

            ("measured_runs > 50 → chặn",
             "SELECT 1",
             {"measured_runs": 100},
             False),

            ("timeout_ms > 60000 → chặn",
             "SELECT 1",
             {"timeout_ms": 70000},
             False),

            ("SQL rỗng → chặn",
             "",
             {},
             False),
        ]

        print("=" * 80)
        print("🧪 TEST TOOL 5 — BENCHMARK_QUERY")
        print("=" * 80)

        passed = 0
        for label, sql, kwargs, expect_ok in cases:
            print(f"\n📌 [{label}]")
            print(f"   SQL: {sql[:70] or '(rỗng)'}")
            print(f"   Args: {kwargs}")

            result = await benchmark_query(sql, **kwargs)
            data = json.loads(result)

            if data["ok"] == expect_ok:
                passed += 1
                status = "✅"
            else:
                status = "❌"

            if data["ok"]:
                d = data["data"]
                print(f"   {status} OK — {data['meta']['duration_ms']}ms")
                print(f"      p50_ms:         {d.get('p50_ms')}")
                print(f"      p95_ms:         {d.get('p95_ms')}")
                print(f"      min/max:        {d.get('min_ms')} / {d.get('max_ms')}")
                print(f"      stddev_ms:      {d.get('stddev_ms')}")
                print(f"      runs:           {d.get('runs')}")
                print(f"      timeouts:       {d.get('timed_out_runs')}")
                print(f"      rows_examined:  {d.get('rows_examined')}")
                print(f"      row_count:      {d.get('row_count')}")
                print(f"      deterministic:  {d.get('deterministic_order')}")
                print(f"      result_hash:    {str(d.get('result_hash'))[:50]}")
            else:
                err = data["error"]
                print(f"   {status} {err['code']}: {err['message'][:60]}")

        print("\n" + "=" * 80)
        print(f"KẾT QUẢ: {passed}/{len(cases)} pass")
        print("=" * 80)

    asyncio.run(run_tests())