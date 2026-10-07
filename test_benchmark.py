"""
Script chạy test Tool 5 từ thư mục gốc project.
Chạy: python test_benchmark.py
"""
import sys
import os
import asyncio
import json

# Đảm bảo project root có trong sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

print(f"📁 Project root: {PROJECT_ROOT}")
print()

# Import tool
try:
    from mcp_server.tools.benchmark import benchmark_query
    print("✅ Import benchmark_query OK")
except Exception as e:
    print(f"❌ Import LỖI: {e}")
    sys.exit(1)

print()


# Test cases
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


async def run_tests():
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
            print(f"      row_count:      {d.get('row_count')}")
            print(f"      deterministic:  {d.get('deterministic_order')}")
            print(f"      result_hash:    {str(d.get('result_hash'))[:50]}")
        else:
            err = data["error"]
            print(f"   {status} {err['code']}: {err['message'][:60]}")

    print("\n" + "=" * 80)
    print(f"KẾT QUẢ: {passed}/{len(cases)} pass")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_tests())