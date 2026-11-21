"""
Chạy 30 query và đo thời gian trên MySQL (Docker).
Mục đích: Xác định query nào đủ chậm (> 0.5s) để làm slow query.
Output: data/outputs/test_queries_result.csv
Phụ trách: Tường | Review: Hải.
Latency lấy từ performance_schema của chính session, không phải thời gian truyền dữ liệu.
Sàng lọc 1 warm-up + 3 lượt đo, chưa phải baseline P95 chính thức.
"""
import csv
import os
import sys

import pymysql
import sqlglot
from sqlglot import exp

# Fix import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.queries.queries import QUERIES
from mcp_server.tools.benchmark import _run_streamed_once
from mcp_server.utils.config import Config
from security.ast_whitelist import check

# ==================== CONFIG ====================
THRESHOLD_SECONDS = 0.5        # Ngưỡng slow query
WARMUP_RUNS = 1                # Chạy warm-up (bỏ)
MEASURE_RUNS = 3               # Số lần đo (lấy trung bình + max)
OUTPUT_CSV = "data/outputs/test_queries_result.csv"
DB_CONFIG = {
    "host": Config.DB_HOST,
    "port": Config.DB_PORT,
    "user": Config.DB_USER,
    "password": Config.DB_PASSWORD,
    "database": Config.DB_NAME,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "connect_timeout": 10,
    "read_timeout": 35,
    "write_timeout": 35,
}


def connect_db():
    """Kết nối MySQL"""
    if DB_CONFIG["user"] != "readonly_user":
        raise ValueError("Script kiểm tra chỉ dùng readonly_user")
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SET SESSION MAX_EXECUTION_TIME = 30000")
            cur.execute("SET SESSION time_zone = '+00:00'")
        return conn
    except (pymysql.MySQLError, OSError) as e:
        if conn is not None:
            conn.close()
        print(f"❌ Không kết nối được MySQL: {type(e).__name__}")
        print("   Kiểm tra: docker compose ps")
        sys.exit(1)


def run_query_once(conn, sql):
    """Chạy 1 query, trả về (duration_ms, rows_examined, row_count)"""
    allowed, reason = check(sql)
    if not allowed:
        raise ValueError(f"AST rejected: {reason}")
    if not isinstance(sqlglot.parse_one(sql, dialect="mysql"), exp.Select):
        raise TypeError("AST: script kiểm tra chỉ nhận SELECT")
    with conn.cursor() as cur:
        cur.execute("SELECT THREAD_ID FROM performance_schema.threads WHERE PROCESSLIST_ID=CONNECTION_ID()")
        thread_id = cur.fetchone()["THREAD_ID"]
    _, _, row_count = _run_streamed_once(conn, sql)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT TIMER_WAIT/1000000000 AS ms, ROWS_EXAMINED AS examined "
            "FROM performance_schema.events_statements_history "
            "WHERE THREAD_ID=%s AND SQL_TEXT=%s ORDER BY EVENT_ID DESC LIMIT 1",
            (thread_id, sql),
        )
        event = cur.fetchone()
    if event is None:
        raise RuntimeError("Không lấy được thời gian phía MySQL")
    if row_count == 0:
        raise ValueError("Query không trả dòng nào; kiểm tra điều kiện lọc")
    return float(event["ms"]), event["examined"], row_count


def test_query(conn, query):
    """Test 1 query: warm-up + đo nhiều lần"""
    query_id = query["id"]
    sql = query["sql"]
    group = query["group"]

    # Đo thật
    durations = []
    last_rows_examined = 0
    last_row_count = 0
    error_msg = None

    try:
        for _ in range(WARMUP_RUNS):
            run_query_once(conn, sql)
        for _ in range(MEASURE_RUNS):
            duration_ms, rows_examined, row_count = run_query_once(conn, sql)
            durations.append(duration_ms)
            last_rows_examined = rows_examined
            last_row_count = row_count
    except (pymysql.MySQLError, OSError, ValueError, TypeError, RuntimeError) as e:
        error_msg = type(e).__name__

    if error_msg:
        return {
            "id": query_id,
            "group": group,
            "avg_ms": None,
            "max_ms": None,
            "rows_examined": None,
            "row_count": None,
            "status": "❌ ERROR",
            "error": error_msg[:200],
        }

    avg_ms = sum(durations) / len(durations)
    max_ms = max(durations)
    is_slow = min(durations) >= THRESHOLD_SECONDS * 1000

    return {
        "id": query_id,
        "group": group,
        "avg_ms": round(avg_ms, 2),
        "max_ms": round(max_ms, 2),
        "rows_examined": last_rows_examined,
        "row_count": last_row_count,
        "status": "✅ SLOW" if is_slow else "⚠️  FAST",
        "error": None,
    }


def main():
    print("=" * 90)
    print("🧪 TEST 30 QUERY TRÊN MYSQL")
    print(f"   Ngưỡng slow: {THRESHOLD_SECONDS}s  |  Đo {MEASURE_RUNS} lần/query")
    print("=" * 90)

    conn = connect_db()

    # Verify kết nối + data
    with conn.cursor() as cur:
        cur.execute(
            "SELECT (SELECT COUNT(*) FROM customers) + (SELECT COUNT(*) FROM addresses) "
            "+ (SELECT COUNT(*) FROM products) + (SELECT COUNT(*) FROM orders) "
            "+ (SELECT COUNT(*) FROM order_items) AS total"
        )
        total_rows = cur.fetchone()["total"]
        print(f"\n📊 Tổng 5 bảng: {total_rows:,} dòng")
        print(f"🐳 MySQL: {DB_CONFIG['host']}:{DB_CONFIG['port']}\n")

    results = []
    slow_count = 0
    fast_count = 0
    error_count = 0

    print(f"{'ID':<6}{'Nhóm':<6}{'Avg(ms)':<10}{'Max(ms)':<10}{'Rows':<14}{'Trạng thái':<12}")
    print("-" * 90)

    for query in QUERIES:
        r = test_query(conn, query)
        results.append(r)

        if r["status"] == "❌ ERROR":
            error_count += 1
            print(f"{r['id']:<6}{r['group']:<6}{'—':<10}{'—':<10}{'—':<14}❌ ERROR")
            print(f"       → {r['error']}")
        else:
            if r["status"] == "✅ SLOW":
                slow_count += 1
            else:
                fast_count += 1
            print(f"{r['id']:<6}{r['group']:<6}{r['avg_ms']:<10}{r['max_ms']:<10}"
                  f"{r['rows_examined']:<14,}{r['status']}")

    # ==================== TỔNG KẾT ====================
    print("\n" + "=" * 90)
    print("📊 TỔNG KẾT")
    print("=" * 90)
    print(f"   ✅ Query đủ chậm (> {THRESHOLD_SECONDS}s): {slow_count}/30")
    print(f"   ⚠️  Query quá nhanh (< {THRESHOLD_SECONDS}s): {fast_count}/30")
    print(f"   ❌ Query lỗi: {error_count}/30")

    if fast_count > 0:
        print(f"\n🚨 CẦN SỬA {fast_count} query sau (chưa đủ chậm):")
        for r in results:
            if r["status"] == "⚠️  FAST":
                print(f"   - {r['id']} (nhóm {r['group']}): {r['avg_ms']}ms")

    if error_count > 0:
        print(f"\n❌ CÓ {error_count} QUERY BỊ LỖI — cần debug:")
        for r in results:
            if r["status"] == "❌ ERROR":
                print(f"   - {r['id']}: {r['error']}")

    # ==================== LƯU CSV ====================
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "group", "avg_ms", "max_ms",
            "rows_examined", "row_count", "status", "error"
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n💾 Kết quả lưu vào: {OUTPUT_CSV}")

    # ==================== GỢI Ý ====================
    if slow_count == 30:
        print("\n🎉 HOÀN HẢO! Cả 30 query đều đủ chậm để test.")
    else:
        print(f"\n⚠️  Chỉ có {slow_count}/30 query đủ chậm. Cần sửa {fast_count} query còn lại.")

    conn.close()
    print("\n" + "=" * 90)
    return 0 if slow_count == len(QUERIES) else 1


if __name__ == "__main__":
    sys.exit(main())
