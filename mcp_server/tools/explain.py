"""
mcp_server/tools/explain.py
---------------------------
CHỨC NĂNG:
    TOOL 4 — explain_query: chạy EXPLAIN FORMAT=JSON để xem query plan.

PHỤ TRÁCH: Hải    |    REVIEW: Vũ

LƯU Ý:
    - Mọi SQL phải qua AST whitelist TRƯỚC khi chạy.
    - mode=estimate: EXPLAIN FORMAT=JSON (không chạy query) — LLM dùng.
    - mode=analyze: EXPLAIN ANALYZE (CÓ chạy query) — chỉ Validation Layer dùng.
    - use_invisible_indexes: LLM KHÔNG được đặt true.
    - Dùng readonly_user + MAX_EXECUTION_TIME.

THAM KHẢO:
    - docs/api-contract.md (Tool 4)
    - project-management/ROADMAP.md (mục 2.2, 2.3)
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
from typing import Optional
from mcp_server.utils.db import get_conn
from mcp_server.utils.logger import get_logger
from mcp_server.utils.config import Config
from security.ast_whitelist import check as ast_check

logger = get_logger(__name__)


# ============================================================
# PARSE EXPLAIN JSON
# ============================================================

def _find_first_table(node) -> Optional[dict]:
    """
    Đệ quy tìm table info đầu tiên trong EXPLAIN plan.
    Hỗ trợ cả cấu trúc đơn giản lẫn nested_loop (JOIN).
    """
    if not isinstance(node, dict):
        return None

    # Case 1: có "table" trực tiếp
    if "table" in node and isinstance(node["table"], dict):
        return node["table"]

    # Case 2: nested_loop (JOIN)
    if "nested_loop" in node:
        for item in node["nested_loop"]:
            found = _find_first_table(item)
            if found:
                return found

    # Case 3: đệ quy vào các nhánh con
    for key in ("query_block", "union_result", "attached_subqueries",
                "materialized_from_subquery", "optimized_away_subqueries"):
        if key in node:
            found = _find_first_table(node[key])
            if found:
                return found

    return None


def _parse_explain_json(raw_json: str) -> dict:
    """
    Parse output EXPLAIN FORMAT=JSON → dict theo contract.

    Returns:
        dict với: query_cost, access_type, key_used,
                  rows_examined_estimate, using_filesort,
                  using_temporary, warnings, raw_plan
    """
    result = {
        "query_cost": None,
        "access_type": None,
        "key_used": None,
        "rows_examined_estimate": None,
        "rows_examined_actual": None,
        "using_filesort": False,
        "using_temporary": False,
        "warnings": [],
        "raw_plan": {},
    }

    # Parse JSON an toàn
    try:
        plan = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
    except (json.JSONDecodeError, TypeError) as e:
        result["warnings"].append(f"Không parse được EXPLAIN JSON: {str(e)[:80]}")
        return result

    if not isinstance(plan, dict):
        result["warnings"].append("EXPLAIN plan không phải dict")
        return result

    result["raw_plan"] = plan

    # Điều hướng vào query_block
    qb = plan.get("query_block", {})

    # Query cost (MySQL 8.0.16+)
    cost_info = qb.get("cost_info", {})
    result["query_cost"] = cost_info.get("query_cost")

    # Tìm table info đầu tiên
    table_info = _find_first_table(qb)

    if table_info:
        result["access_type"] = table_info.get("access_type")
        result["key_used"] = table_info.get("key")
        result["rows_examined_estimate"] = table_info.get("rows_examined_per_scan")
        result["using_filesort"] = "using_filesort" in table_info
        result["using_temporary"] = "using_temporary_table" in table_info

        # Cảnh báo full scan
        access_type = result["access_type"]
        if access_type == "ALL":
            tbl = table_info.get("table_name", "?")
            result["warnings"].append(f"Full table scan on {tbl}")
        elif access_type == "index":
            tbl = table_info.get("table_name", "?")
            result["warnings"].append(f"Full index scan on {tbl}")

        # Cảnh báo filesort
        if result["using_filesort"]:
            result["warnings"].append("Using filesort")

    return result


def _parse_explain_analyze(raw_text: str) -> dict:
    """
    Parse output EXPLAIN ANALYZE (trả về text, không phải JSON).
    Chỉ lấy những thông tin cơ bản.
    """
    result = {
        "query_cost": None,
        "access_type": None,
        "key_used": None,
        "rows_examined_estimate": None,
        "rows_examined_actual": None,
        "using_filesort": False,
        "using_temporary": False,
        "warnings": [],
        "raw_plan": {"analyze_text": str(raw_text)},
    }

    if not raw_text:
        result["warnings"].append("EXPLAIN ANALYZE không có output")
        return result

    text_lower = str(raw_text).lower()

    if "filesort" in text_lower:
        result["using_filesort"] = True
        result["warnings"].append("Using filesort (từ ANALYZE text)")

    if "temporary" in text_lower:
        result["using_temporary"] = True

    if "table scan" in text_lower or "full scan" in text_lower:
        result["access_type"] = "ALL"
        result["warnings"].append("Full table scan (từ ANALYZE text)")

    return result


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
            "tool": "explain_query",
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 2),
            "truncated": False,
        },
    }, ensure_ascii=False)


# ============================================================
# MAIN TOOL FUNCTION
# ============================================================

async def explain_query(
    sql: str,
    mode: str = "estimate",
    use_invisible_indexes: bool = False,
) -> str:
    """
    Chạy EXPLAIN FORMAT=JSON cho câu SQL.

    Args:
        sql: Câu SQL cần phân tích (chỉ SELECT)
        mode: "estimate" | "analyze"
              - estimate: EXPLAIN FORMAT=JSON (không chạy query) — LLM dùng
              - analyze: EXPLAIN ANALYZE (chạy thật) — chỉ Validation Layer
        use_invisible_indexes: bật use_invisible_indexes (chỉ Validation Layer)

    Returns:
        JSON string theo contract api-contract.md mục Tool 4
    """
    t_start = time.perf_counter()

    # ------------------------------------------------
    # BƯỚC 1: Validate input
    # ------------------------------------------------
    if not sql or not sql.strip():
        return _error_response("INVALID_INPUT", "sql rỗng", t_start)

    if mode not in ("estimate", "analyze"):
        return _error_response(
            "INVALID_INPUT",
            f"mode không hợp lệ: '{mode}'. Chỉ nhận 'estimate' hoặc 'analyze'",
            t_start,
        )

    # ------------------------------------------------
    # BƯỚC 2: Check AST whitelist (fail-closed)
    # ------------------------------------------------
    ok, reason = ast_check(sql)
    if not ok:
        logger.warning(f"[explain_query] AST_REJECTED: {reason}")
        return _error_response("AST_REJECTED", reason, t_start)

    # ------------------------------------------------
    # BƯỚC 3: Xây câu EXPLAIN
    # ------------------------------------------------
    if mode == "analyze":
        explain_sql = f"EXPLAIN ANALYZE {sql}"
    else:
        explain_sql = f"EXPLAIN FORMAT=JSON {sql}"

    # ------------------------------------------------
    # BƯỚC 4: Chạy qua readonly_user
    # ------------------------------------------------
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                # Set timeout để không treo hệ thống
                cur.execute(
                    f"SET SESSION MAX_EXECUTION_TIME = {Config.MAX_EXECUTION_TIME}"
                )

                # Bật use_invisible_indexes (chỉ Validation Layer)
                if use_invisible_indexes:
                    cur.execute(
                        "SET SESSION optimizer_switch = 'use_invisible_indexes=on'"
                    )

                # Chạy EXPLAIN
                cur.execute(explain_sql)
                row = cur.fetchone()

                if not row:
                    return _error_response(
                        "INTERNAL", "EXPLAIN trả về rỗng", t_start
                    )

                # Lấy raw output (key có thể là 'EXPLAIN' hoặc key khác)
                raw_output = (
                    row.get("EXPLAIN")
                    or row.get("explain")
                    or list(row.values())[0]
                )

                # Parse theo mode
                if mode == "analyze":
                    data = _parse_explain_analyze(raw_output)
                else:
                    data = _parse_explain_json(raw_output)

        # ------------------------------------------------
        # BƯỚC 5: Trả kết quả
        # ------------------------------------------------
        duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.info(
            f"[explain_query] mode={mode} OK | {duration_ms}ms | "
            f"access_type={data.get('access_type')} | "
            f"key={data.get('key_used')}"
        )

        return json.dumps({
            "ok": True,
            "data": data,
            "error": None,
            "meta": {
                "tool": "explain_query",
                "duration_ms": duration_ms,
                "truncated": False,
            },
        }, ensure_ascii=False, default=str)

    except Exception as e:
        err_msg = str(e)[:200]
        logger.error(f"[explain_query] ERROR: {err_msg}")

        # Phân loại lỗi
        if "maximum statement execution time" in err_msg.lower():
            return _error_response("TIMEOUT", err_msg, t_start)
        return _error_response("INTERNAL", err_msg, t_start)


# ============================================================
# TEST NHANH — CHẠY FILE TRỰC TIẾP
# ============================================================

if __name__ == "__main__":
    import asyncio

    async def run_tests():
        # Các case test
        cases = [
            # (label, sql, mode, expect_ok)
            ("Query giống case study",
             "SELECT SUM(total_revenue) FROM sales_data "
             "WHERE region = 'Asia' AND order_date >= '2024-01-01'",
             "estimate", True),

            ("Query đơn giản",
             "SELECT * FROM sales_data WHERE region = 'Asia'",
             "estimate", True),

            ("Query có JOIN (self-join)",
             "SELECT s1.id FROM sales_data s1 "
             "JOIN sales_data s2 ON s2.region = s1.region "
             "WHERE s2.total_profit > 10000",
             "estimate", True),

            ("DROP TABLE → chặn",
             "DROP TABLE sales_data", "estimate", False),

            ("Multi-statement → chặn",
             "SELECT 1; DROP TABLE sales_data", "estimate", False),

            ("SQL rỗng → chặn",
             "", "estimate", False),

            ("mode sai → chặn",
             "SELECT 1", "invalid_mode", False),
        ]

        print("=" * 80)
        print("🧪 TEST TOOL 4 — EXPLAIN_QUERY")
        print("=" * 80)

        passed = 0
        for label, sql, mode, expect_ok in cases:
            print(f"\n📌 [{label}]")
            print(f"   SQL: {sql[:70] or '(rỗng)'}")
            print(f"   mode: {mode}")

            result = await explain_query(sql, mode=mode)
            data = json.loads(result)

            if data["ok"] == expect_ok:
                passed += 1
                status = "✅"
            else:
                status = "❌"

            if data["ok"]:
                d = data["data"]
                print(f"   {status} OK — {data['meta']['duration_ms']}ms")
                print(f"      query_cost:     {d.get('query_cost')}")
                print(f"      access_type:    {d.get('access_type')}")
                print(f"      key_used:       {d.get('key_used')}")
                print(f"      rows_examined:  {d.get('rows_examined_estimate')}")
                print(f"      using_filesort: {d.get('using_filesort')}")
                print(f"      warnings:       {d.get('warnings')}")
            else:
                err = data["error"]
                print(f"   {status} {err['code']}: {err['message'][:60]}")

        print("\n" + "=" * 80)
        print(f"KẾT QUẢ: {passed}/{len(cases)} pass")
        print("=" * 80)

    asyncio.run(run_tests())