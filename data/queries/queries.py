"""
30 query chậm — Tường phụ trách.
Dataset: shopdb.sales_data (5M dòng)
Người làm: Tường
Reviewer: Hải

Nhóm 1: Thiếu index (q01-q06)
Nhóm 2: Sai thứ tự cột composite (q07-q12)
Nhóm 3: Hàm bọc cột - non-sargable (q13-q18)
Nhóm 4: SELECT * + filesort (q19-q24)
Nhóm 5: Subquery → JOIN (self-join, q25-q30)
"""

QUERIES = [
    # ============================================================
    # NHÓM 1: THIẾU INDEX (6 query)
    # Bản chất: WHERE lọc trên cột KHÔNG có index → full scan 5M dòng
    # Cách sửa: Thêm index trên cột lọc
    # ============================================================
    {
        "id": "q01",
        "group": 1,
        "description": "Lọc theo region, không có index → full scan 5M dòng",
        "sql": "SELECT id, country, item_type, total_revenue FROM sales_data WHERE region = 'Asia' LIMIT 100",
        "expected_answer_type": "index",
        "expected_index_hint": ["region"],
    },
    {
        "id": "q02",
        "group": 1,
        "description": "Lọc theo country, không có index",
        "sql": "SELECT id, region, item_type, total_profit FROM sales_data WHERE country = 'Vietnam'",
        "expected_answer_type": "index",
        "expected_index_hint": ["country"],
    },
    {
        "id": "q03",
        "group": 1,
        "description": "Lọc theo item_type, không có index",
        "sql": "SELECT id, region, country, total_revenue FROM sales_data WHERE item_type = 'Fruits'",
        "expected_answer_type": "index",
        "expected_index_hint": ["item_type"],
    },
    {
        "id": "q04",
        "group": 1,
        "description": "Lọc theo sales_channel, không có index",
        "sql": "SELECT id, region, total_revenue, total_profit FROM sales_data WHERE sales_channel = 'Online'",
        "expected_answer_type": "index",
        "expected_index_hint": ["sales_channel"],
    },
    {
        "id": "q05",
        "group": 1,
        "description": "Lọc theo order_priority, không có index",
        "sql": "SELECT id, region, total_revenue FROM sales_data WHERE order_priority = 'H'",
        "expected_answer_type": "index",
        "expected_index_hint": ["order_priority"],
    },
    {
        "id": "q06",
        "group": 1,
        "description": "Lọc theo order_id, không có index (order_id không phải PK)",
        "sql": "SELECT id, region, item_type, total_revenue FROM sales_data WHERE order_id = 123456789",
        "expected_answer_type": "index",
        "expected_index_hint": ["order_id"],
    },

    # ============================================================
    # NHÓM 2: SAI THỨ TỰ CỘT COMPOSITE (6 query)
    # Bản chất: Query có equality + range, index đặt SAI thứ tự
    # Quy tắc vàng: EQUALITY TRƯỚC, RANGE SAU
    # ============================================================
    {
        "id": "q07",
        "group": 2,
        "description": "CASE STUDY: equality region + range order_date. Đề bài ghi (order_date, region) nhưng quy tắc là (region, order_date)",
        "sql": "SELECT id, country, item_type, total_revenue FROM sales_data WHERE region = 'Asia' AND order_date >= '2024-01-01' AND order_date < '2025-01-01'",
        "expected_answer_type": "index",
        "expected_index_hint": ["region", "order_date"],
        "note": "PHẢI đo thật ở tuần 3 để kết luận có số liệu — điểm ăn tiền học thuật",
    },
    {
        "id": "q08",
        "group": 2,
        "description": "2 equality: region + country",
        "sql": "SELECT id, item_type, total_revenue FROM sales_data WHERE region = 'Asia' AND country = 'Vietnam'",
        "expected_answer_type": "index",
        "expected_index_hint": ["region", "country"],
    },
    {
        "id": "q09",
        "group": 2,
        "description": "equality region + range total_revenue",
        "sql": "SELECT id, country, total_profit FROM sales_data WHERE region = 'Asia' AND total_revenue > 5000",
        "expected_answer_type": "index",
        "expected_index_hint": ["region", "total_revenue"],
    },
    {
        "id": "q10",
        "group": 2,
        "description": "equality order_priority + range order_date",
        "sql": "SELECT id, region, total_revenue FROM sales_data WHERE order_priority = 'H' AND order_date > '2024-06-01'",
        "expected_answer_type": "index",
        "expected_index_hint": ["order_priority", "order_date"],
    },
    {
        "id": "q11",
        "group": 2,
        "description": "equality item_type + range total_profit",
        "sql": "SELECT id, region, total_revenue FROM sales_data WHERE item_type = 'Fruits' AND total_profit > 500",
        "expected_answer_type": "index",
        "expected_index_hint": ["item_type", "total_profit"],
    },
    {
        "id": "q12",
        "group": 2,
        "description": "equality sales_channel + range order_date",
        "sql": "SELECT id, region, total_revenue FROM sales_data WHERE sales_channel = 'Online' AND order_date > '2024-06-01'",
        "expected_answer_type": "index",
        "expected_index_hint": ["sales_channel", "order_date"],
    },

    # ============================================================
    # NHÓM 3: HÀM BỌC CỘT - NON-SARGABLE (6 query)
    # Bản chất: Dùng hàm quanh cột → MySQL không dùng được index
    # Cách sửa: Rewrite thành range/comparison trực tiếp
    # ============================================================
    {
        "id": "q13",
        "group": 3,
        "description": "YEAR() bọc cột order_date → không dùng được index",
        "sql": "SELECT COUNT(*) AS total FROM sales_data WHERE YEAR(order_date) = 2024 AND region = 'Asia'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển YEAR(order_date) = 2024 thành order_date >= '2024-01-01' AND order_date < '2025-01-01'",
    },
    {
        "id": "q14",
        "group": 3,
        "description": "MONTH() bọc cột order_date",
        "sql": "SELECT COUNT(*) FROM sales_data WHERE MONTH(order_date) = 11",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "MONTH() không có năm → cần query riêng theo năm hoặc UNION. Có thể chuyển thành range nếu biết năm",
    },
    {
        "id": "q15",
        "group": 3,
        "description": "DATE() bọc cột order_date",
        "sql": "SELECT id, region, total_revenue FROM sales_data WHERE DATE(order_date) = '2024-11-29'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành order_date = '2024-11-29' (vì order_date đã là DATE, DATE() thừa) hoặc range nếu là DATETIME",
    },
    {
        "id": "q16",
        "group": 3,
        "description": "UPPER() bọc cột country",
        "sql": "SELECT id, region, total_revenue FROM sales_data WHERE UPPER(country) = 'VIETNAM'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Dùng collation case-insensitive (utf8mb4_general_ci) hoặc lưu lowercase",
    },
    {
        "id": "q17",
        "group": 3,
        "description": "Toán tử + trên cột total_revenue",
        "sql": "SELECT id, region, country FROM sales_data WHERE total_revenue + 100 > 5000",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành total_revenue > 4900 (đảo phép toán)",
    },
    {
        "id": "q18",
        "group": 3,
        "description": "LEFT() bọc cột region",
        "sql": "SELECT id, country, total_revenue FROM sales_data WHERE LEFT(region, 3) = 'Asi'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Dùng region LIKE 'Asi%' — MySQL dùng được index prefix",
    },

    # ============================================================
    # NHÓM 4: SELECT * + FILESORT (6 query)
    # Bản chất: SELECT * đọc nhiều cột + ORDER BY không index → filesort
    # Cách sửa: Thêm index trên cột ORDER BY (và WHERE)
    # ============================================================
    {
        "id": "q19",
        "group": 4,
        "description": "SELECT * + ORDER BY order_date DESC",
        "sql": "SELECT * FROM sales_data WHERE region = 'Asia' ORDER BY order_date DESC LIMIT 50",
        "expected_answer_type": "index",
        "expected_index_hint": ["region", "order_date"],
    },
    {
        "id": "q20",
        "group": 4,
        "description": "SELECT * + ORDER BY units_sold DESC",
        "sql": "SELECT * FROM sales_data WHERE country = 'Vietnam' ORDER BY units_sold DESC",
        "expected_answer_type": "index",
        "expected_index_hint": ["country", "units_sold"],
    },
    {
        "id": "q21",
        "group": 4,
        "description": "SELECT * + ORDER BY total_revenue DESC",
        "sql": "SELECT * FROM sales_data WHERE item_type = 'Fruits' ORDER BY total_revenue DESC",
        "expected_answer_type": "index",
        "expected_index_hint": ["item_type", "total_revenue"],
    },
    {
        "id": "q22",
        "group": 4,
        "description": "SELECT * + ORDER BY order_date ASC",
        "sql": "SELECT * FROM sales_data WHERE sales_channel = 'Online' ORDER BY order_date ASC",
        "expected_answer_type": "index",
        "expected_index_hint": ["sales_channel", "order_date"],
    },
    {
        "id": "q23",
        "group": 4,
        "description": "SELECT * + ORDER BY total_profit DESC",
        "sql": "SELECT * FROM sales_data WHERE order_priority = 'H' ORDER BY total_profit DESC",
        "expected_answer_type": "index",
        "expected_index_hint": ["order_priority", "total_profit"],
    },
    {
        "id": "q24",
        "group": 4,
        "description": "SELECT * KHÔNG WHERE → full scan + filesort toàn bảng",
        "sql": "SELECT * FROM sales_data ORDER BY order_date DESC LIMIT 100",
        "expected_answer_type": "index",
        "expected_index_hint": ["order_date"],
    },

    # ============================================================
    # NHÓM 5: SUBQUERY → JOIN (SELF-JOIN vì chỉ có 1 bảng) (6 query)
    # Bản chất: Subquery không tối ưu → rewrite thành self-join
    # Lưu ý: MySQL 8 tự chuyển 1 số IN → semijoin, cần test thật
    # ============================================================
    {
        "id": "q25",
        "group": 5,
        "description": "IN subquery → chuyển self-join",
        "sql": "SELECT id, region, country FROM sales_data WHERE region IN (SELECT region FROM sales_data WHERE total_profit > 10000)",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành self-join sales_data s1 JOIN sales_data s2 ON s2.region = s1.region WHERE s2.total_profit > 10000, kèm DISTINCT",
    },
    {
        "id": "q26",
        "group": 5,
        "description": "NOT IN subquery → chuyển LEFT JOIN IS NULL",
        "sql": "SELECT id, region FROM sales_data WHERE order_id NOT IN (SELECT order_id FROM sales_data WHERE order_priority = 'C')",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành LEFT JOIN sales_data s2 ON s2.order_id = s1.order_id AND s2.order_priority = 'C' WHERE s2.id IS NULL",
    },
    {
        "id": "q27",
        "group": 5,
        "description": "EXISTS correlated subquery → chuyển self-join",
        "sql": "SELECT id, region, total_profit FROM sales_data s1 WHERE EXISTS (SELECT 1 FROM sales_data s2 WHERE s2.region = s1.region AND s2.total_revenue > 50000)",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành self-join kèm DISTINCT",
    },
    {
        "id": "q28",
        "group": 5,
        "description": "Correlated subquery trong SELECT → chạy N lần",
        "sql": "SELECT s1.region, s1.country, (SELECT COUNT(*) FROM sales_data s2 WHERE s2.region = s1.region) AS region_count FROM sales_data s1 WHERE s1.order_priority = 'H'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành self-join + GROUP BY",
    },
    {
        "id": "q29",
        "group": 5,
        "description": "IN subquery lồng 2 cấp → self-join 3 lần",
        "sql": "SELECT id, region, item_type FROM sales_data WHERE item_type IN (SELECT item_type FROM sales_data WHERE country IN (SELECT country FROM sales_data WHERE sales_channel = 'Online'))",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành self-join 3 lần sales_data s1/s2/s3, kèm DISTINCT",
    },
    {
        "id": "q30",
        "group": 5,
        "description": "Subquery trong FROM → derived table",
        "sql": "SELECT * FROM (SELECT region, SUM(total_revenue) AS total FROM sales_data GROUP BY region) AS t WHERE t.total > 1000000",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành GROUP BY region HAVING SUM(total_revenue) > 1000000",
    },
]


# ============================================================
# HÀM HELPER
# ============================================================

def get_all_queries():
    """Lấy tất cả 30 query."""
    return QUERIES


def get_queries_by_group(group: int):
    """Lấy tất cả query thuộc 1 nhóm (1-5)."""
    return [q for q in QUERIES if q["group"] == group]


def get_query_by_id(query_id: str):
    """Lấy 1 query theo id (q01..q30)."""
    for q in QUERIES:
        if q["id"] == query_id:
            return q
    return None


def get_queries_by_type(answer_type: str):
    """Lấy query theo loại đáp án (index/rewrite)."""
    return [q for q in QUERIES if q["expected_answer_type"] == answer_type]


def get_index_queries():
    """Lấy query cần index (nhóm 1, 2, 4)."""
    return [q for q in QUERIES if q["expected_answer_type"] == "index"]


def get_rewrite_queries():
    """Lấy query cần rewrite (nhóm 3, 5)."""
    return [q for q in QUERIES if q["expected_answer_type"] == "rewrite"]


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("KIỂM TRA 30 QUERY — DATASET sales_data")
    print("=" * 60)

    print(f"\n📊 Tổng số query: {len(QUERIES)}")

    if len(QUERIES) != 30:
        print(f"⚠️  CẢNH BÁO: Phải có đúng 30 query, hiện có {len(QUERIES)}")

    print("\n📋 Phân bố theo nhóm:")
    for g in range(1, 6):
        qs = get_queries_by_group(g)
        status = "✅" if len(qs) == 6 else "❌"
        print(f"   {status} Nhóm {g}: {len(qs)} query")

    print("\n📋 Phân bố theo loại đáp án:")
    print(f"   - Index (nhóm 1,2,4): {len(get_index_queries())} query")
    print(f"   - Rewrite (nhóm 3,5): {len(get_rewrite_queries())} query")

    print("\n📋 Danh sách ID:")
    ids = [q["id"] for q in QUERIES]
    print(f"   {', '.join(ids)}")

    print("\n" + "=" * 60)
    print("✅ HOÀN THÀNH" if len(QUERIES) == 30 else "❌ CHƯA ĐỦ 30 QUERY")
    print("=" * 60)