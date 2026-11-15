"""
scripts/seed_demo_dashboard.py
------------------------------
CHỨC NĂNG:
    Tạo DỮ LIỆU DEMO cho Dashboard (proposals + validation report giả) để kiểm giao diện
    và quay video dự phòng khi chưa có LLM agent / Validation Layer / MySQL.

PHỤ TRÁCH: Tình    |    REVIEW: Tường

AN TOÀN:
    - CHỈ ghi vào data/meta/demo.sqlite3 (không đụng DB meta thật).
    - Dashboard tự hiện banner "dữ liệu demo" khi META_DB_PATH chứa chữ 'demo'.
    - Số liệu là GIẢ, không được dùng trong báo cáo.

CHẠY:
    python scripts/seed_demo_dashboard.py
    META_DB_PATH=data/meta/demo.sqlite3 streamlit run dashboard/app.py         (bash)
    $env:META_DB_PATH="data/meta/demo.sqlite3"; streamlit run dashboard/app.py  (PowerShell)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEMO_DB = ROOT / "data" / "meta" / "demo.sqlite3"


def main():
    if DEMO_DB.exists():
        DEMO_DB.unlink()
    os.environ["META_DB_PATH"] = str(DEMO_DB)
    from mcp_server.store import proposals as store

    def index(q, cols, name, before, after, size_mb, ins_pct, status="passed", eq=True, reason=None):
        pid = store.save_proposal({
            "type": "index", "table": "sales_data", "columns": cols, "index_name": name,
            "rationale": f"[DEMO] đề xuất cho {q}", "target_query_ids": [q],
        }, source="demo")
        store.save_validation_report(pid, {
            "proposal_id": pid, "status": status,
            "before": {"p95_ms": before, "query_cost": before * 520, "rows_examined": 5_000_000},
            "after": {"p95_ms": after, "query_cost": after * 40, "rows_examined": int(5_000_000 * after / before)},
            "result_equivalent": eq,
            "improvement_ratio": round(1 - after / before, 3),
            "write_overhead": {"insert_throughput_change_pct": ins_pct,
                               "index_size_bytes": int(size_mb * 1024 * 1024)},
            "failure_reason": reason,
        })
        return pid

    index("q01", ["region"], "idx_sales_region", 2310, 180, 92, -3.1)
    index("q07", ["region", "order_date"], "idx_sales_region_date", 2890, 41, 131, -5.4)
    index("q10", ["order_priority", "order_date"], "idx_sales_priority_date", 2650, 63, 118, -4.8)
    index("q04", ["sales_channel"], "idx_sales_channel", 1980, 1760, 75, -2.9, status="failed",
          reason="[DEMO] P95 chỉ giảm 11% (< 20%) — cardinality thấp")
    store.save_proposal({"type": "index", "table": "sales_data", "columns": ["country"],
                         "index_name": "idx_sales_country", "rationale": "[DEMO] chờ validation",
                         "target_query_ids": ["q02"]}, source="demo")
    rw = store.save_proposal({"type": "rewrite", "original_query_id": "q13",
                              "rewritten_sql": "SELECT id, region FROM sales_data "
                                               "WHERE order_date >= '2020-01-01' AND order_date < '2021-01-01'",
                              "rationale": "[DEMO] bỏ YEAR(order_date) để dùng được index"}, source="demo")
    store.save_validation_report(rw, {"status": "passed", "before": {"p95_ms": 2400},
                                      "after": {"p95_ms": 95}, "result_equivalent": True,
                                      "improvement_ratio": 0.96})
    print(f"Đã tạo dữ liệu demo: {DEMO_DB}")


if __name__ == "__main__":
    main()
