"""
Chạy 30 query và đo thời gian trên MySQL (Docker).
Mục đích: Xác định query nào đủ chậm (> 0.5s) để làm slow query.
Output: data/outputs/test_queries_result.csv
"""
import sys
import os
import time
import csv
import pymysql
from datetime import datetime

# Fix import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.queries.queries import QUERIES
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIG ====================
THRESHOLD_SECONDS = 0.5        # Ngưỡng slow query
WARMUP_RUNS = 1                # Chạy warm-up (bỏ)
MEASURE_RUNS = 3               # Số lần đo (lấy trung bình + max)
OUTPUT_CSV = "data/outputs/test_queries_result.csv"
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3307)),       # Port 3307 (Docker)
    "user": "root",
    "password": os.getenv("MYSQL_ROOT_PASSWORD", "root"),
    "database": os.getenv("MYSQL_DATABASE", "shopdb"),
    "charset": "utf8mb4",
}


def connect_db():
    """Kết nối MySQL"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Không kết nối được MySQL: {e}")
        print(f"   Kiểm tra: docker compose ps")
        sys.exit(1)


def run_query_once(conn, sql):
    """Chạy 1 query, trả về (duration_ms, rows_examined, row_count)"""
    with conn.cursor() as cur:
        # Reset counter rows_examined của session
        cur.execute("FLUSH STATUS")

        # Chạy query và đo thời gian
        t_start = time.perf_counter()
        cur.execute(sql)
        rows = cur.fetchall()
        t_end = time.perf_counter()

        duration_ms = (t_end - t_start) * 1000
        row_count = len(rows)

        # Lấy rows_examined
        cur.execute("SHOW SESSION STATUS LIKE 'Handler_read%'")
        rows_examined = sum(int(row[1]) for row in cur.fetchall())

    return duration_ms, rows_examined, row_count


def test_query(conn, query):
    """Test 1 query: warm-up + đo nhiều lần"""
    query_id = query["id"]
    sql = query["sql"]
    group = query["group"]

    # Warm-up (bỏ kết quả)
    for _ in range(WARMUP_RUNS):
        try:
            run_query_once(conn, sql)
        except Exception:
            pass

    # Đo thật
    durations = []
    last_rows_examined = 0
    last_row_count = 0
    error_msg = None

    for i in range(MEASURE_RUNS):
        try:
            duration_ms, rows_examined, row_count = run_query_once(conn, sql)
            durations.append(duration_ms)
            last_rows_examined = rows_examined
            last_row_count = row_count
        except Exception as e:
            error_msg = str(e)
            break

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
    is_slow = avg_ms >= THRESHOLD_SECONDS * 1000

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
        cur.execute("SELECT COUNT(*) FROM sales_data")
        total_rows = cur.fetchone()[0]
        print(f"\n📊 Bảng sales_data: {total_rows:,} dòng")
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
    elif slow_count >= 24:
        print(f"\n✅ ỔN! {slow_count}/30 query đủ chậm (≥ 80%). Có thể dùng được.")
    else:
        print(f"\n⚠️  Chỉ có {slow_count}/30 query đủ chậm. Cần sửa {fast_count} query còn lại.")

    conn.close()
    print("\n" + "=" * 90)


if __name__ == "__main__":
    main()