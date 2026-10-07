"""
30 query chậm — Tường phụ trách.
Người làm: Tường
Reviewer: Hải

Nhóm 1: Thiếu index (q01-q06)
Nhóm 2: Sai thứ tự cột composite (q07-q12)
Nhóm 3: Hàm bọc cột - non-sargable (q13-q18)
Nhóm 4: SELECT * + filesort (q19-q24)
Nhóm 5: Subquery → JOIN (q25-q30)

Mỗi query có:
- id: q01..q30
- group: 1..5
- description: mô tả lỗi
- sql: câu SQL
- expected_answer_type: "index" | "rewrite"
- expected_index_hint (nếu index): gợi ý cột
- rewrite_hint (nếu rewrite): gợi ý viết lại
"""

QUERIES = [
    # ============================================================
    # NHÓM 1: THIẾU INDEX (6 query)
    # Bản chất: WHERE lọc trên cột KHÔNG có index → full table scan
    # Cách sửa: Thêm index trên cột lọc
    # ============================================================
    {
        "id": "q01",
        "group": 1,
        "description": "Lọc đơn hàng theo status, không có index trên status → full scan 12M dòng",
        "sql": "SELECT id, user_id, total_amount, created_at FROM orders WHERE status = 'completed' LIMIT 100",
        "expected_answer_type": "index",
        "expected_index_hint": ["status"],
        "note": "status là cột lọc phổ biến, chưa có index",
    },
    {
        "id": "q02",
        "group": 1,
        "description": "Lọc user theo email, không có index → full scan users",
        "sql": "SELECT id, email, full_name FROM users WHERE email = 'user123@example.com'",
        "expected_answer_type": "index",
        "expected_index_hint": ["email"],
        "note": "email thường unique, index rất hiệu quả",
    },
    {
        "id": "q03",
        "group": 1,
        "description": "Lọc order_items theo product_id, không có index → full scan 20M dòng",
        "sql": "SELECT id, order_id, quantity, price FROM order_items WHERE product_id = 12345",
        "expected_answer_type": "index",
        "expected_index_hint": ["product_id"],
        "note": "order_items có 20M dòng, full scan rất chậm",
    },
    {
        "id": "q04",
        "group": 1,
        "description": "Lọc products theo category_id, không có index",
        "sql": "SELECT id, name, price FROM products WHERE category_id = 5",
        "expected_answer_type": "index",
        "expected_index_hint": ["category_id"],
        "note": "category_id là FK, thường thiếu index",
    },
    {
        "id": "q05",
        "group": 1,
        "description": "Lọc orders theo user_id, không có index",
        "sql": "SELECT id, total_amount, status FROM orders WHERE user_id = 98765",
        "expected_answer_type": "index",
        "expected_index_hint": ["user_id"],
        "note": "user_id là FK, query phổ biến",
    },
    {
        "id": "q06",
        "group": 1,
        "description": "Lọc users theo city, không có index",
        "sql": "SELECT id, email, full_name FROM users WHERE city = 'Hanoi'",
        "expected_answer_type": "index",
        "expected_index_hint": ["city"],
        "note": "city có cardinality thấp, index có thể không hiệu quả nếu phân bố đều — cần đo",
    },

    # ============================================================
    # NHÓM 2: SAI THỨ TỰ CỘT COMPOSITE (6 query)
    # Bản chất: Query có equality + range, index đặt SAI thứ tự
    # Quy tắc vàng: EQUALITY TRƯỚC, RANGE SAU
    # ============================================================
    {
        "id": "q07",
        "group": 2,
        "description": "CASE STUDY BLACK FRIDAY: range trên created_at + equality trên status. Đề bài ghi (created_at, status), nhưng quy tắc là (status, created_at)",
        "sql": "SELECT id, user_id, total_amount FROM orders WHERE created_at >= '2024-11-29 00:00:00' AND created_at < '2024-11-30 00:00:00' AND status = 'completed'",
        "expected_answer_type": "index",
        "expected_index_hint": ["status", "created_at"],
        "note": "PHẢI đo thật ở tuần 3 để kết luận có số liệu — đây là điểm ăn tiền học thuật",
    },
    {
        "id": "q08",
        "group": 2,
        "description": "Equality trên status + user_id, thứ tự (status, user_id)",
        "sql": "SELECT id, total_amount FROM orders WHERE status = 'pending' AND user_id = 12345",
        "expected_answer_type": "index",
        "expected_index_hint": ["status", "user_id"],
        "note": "2 equality → thứ tự ít quan trọng, nhưng status có cardinality thấp hơn → đặt sau? Cần đo",
    },
    {
        "id": "q09",
        "group": 2,
        "description": "Equality status + range total_amount",
        "sql": "SELECT id, user_id FROM orders WHERE status = 'completed' AND total_amount > 5000000",
        "expected_answer_type": "index",
        "expected_index_hint": ["status", "total_amount"],
        "note": "Equality (status) trước, range (total_amount) sau",
    },
    {
        "id": "q10",
        "group": 2,
        "description": "Equality status + range created_at + ORDER BY created_at DESC",
        "sql": "SELECT id, user_id FROM orders WHERE status = 'completed' AND created_at > '2024-01-01' ORDER BY created_at DESC LIMIT 50",
        "expected_answer_type": "index",
        "expected_index_hint": ["status", "created_at"],
        "note": "Index (status, created_at) cũng giúp ORDER BY vì created_at trong index đã sorted",
    },
    {
        "id": "q11",
        "group": 2,
        "description": "Equality category_id + range price",
        "sql": "SELECT id, name FROM products WHERE category_id = 3 AND price > 100000",
        "expected_answer_type": "index",
        "expected_index_hint": ["category_id", "price"],
        "note": "Equality trước, range sau",
    },
    {
        "id": "q12",
        "group": 2,
        "description": "Equality status + payment_method (2 equality)",
        "sql": "SELECT id, total_amount FROM orders WHERE status = 'completed' AND payment_method = 'credit_card'",
        "expected_answer_type": "index",
        "expected_index_hint": ["status", "payment_method"],
        "note": "2 equality → thứ tự có thể đảo, cần đo. payment_method có cardinality thấp hơn",
    },

    # ============================================================
    # NHÓM 3: HÀM BỌC CỘT - NON-SARGABLE (6 query)
    # Bản chất: Dùng hàm quanh cột → MySQL không dùng được index
    # Cách sửa: Rewrite thành range/comparison trực tiếp
    # ============================================================
    {
        "id": "q13",
        "group": 3,
        "description": "Dùng YEAR() bọc cột created_at → không dùng được index",
        "sql": "SELECT COUNT(*) AS total FROM orders WHERE YEAR(created_at) = 2024 AND status = 'completed'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển YEAR(created_at) = 2024 thành created_at >= '2024-01-01' AND created_at < '2025-01-01'",
    },
    {
        "id": "q14",
        "group": 3,
        "description": "Dùng MONTH() bọc cột created_at",
        "sql": "SELECT COUNT(*) FROM orders WHERE MONTH(created_at) = 11",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành range trên created_at, ví dụ cho tháng 11 mọi năm: cần UNION hoặc query riêng theo năm",
    },
    {
        "id": "q15",
        "group": 3,
        "description": "Dùng DATE() bọc cột created_at",
        "sql": "SELECT id, user_id FROM orders WHERE DATE(created_at) = '2024-11-29'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành created_at >= '2024-11-29 00:00:00' AND created_at < '2024-11-30 00:00:00'",
    },
    {
        "id": "q16",
        "group": 3,
        "description": "Dùng UPPER() bọc cột email",
        "sql": "SELECT id, full_name FROM users WHERE UPPER(email) = 'USER123@EXAMPLE.COM'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Dùng collation case-insensitive (utf8mb4_general_ci) hoặc lưu email lowercase",
    },
    {
        "id": "q17",
        "group": 3,
        "description": "Toán tử + trên cột total_amount",
        "sql": "SELECT id, user_id FROM orders WHERE total_amount + 100 > 5000000",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành total_amount > 4999900 (đảo phép toán)",
    },
    {
        "id": "q18",
        "group": 3,
        "description": "Dùng LEFT() bọc cột full_name",
        "sql": "SELECT id, email FROM users WHERE LEFT(full_name, 3) = 'Ngu'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Dùng full_name LIKE 'Ngu%' — MySQL dùng được index prefix",
    },

    # ============================================================
    # NHÓM 4: SELECT * + FILESORT (6 query)
    # Bản chất: SELECT * đọc nhiều cột + ORDER BY không index → filesort
    # Cách sửa: Thêm index trên cột ORDER BY (và WHERE)
    # ============================================================
    {
        "id": "q19",
        "group": 4,
        "description": "SELECT * + ORDER BY created_at không index → filesort",
        "sql": "SELECT * FROM orders WHERE user_id = 12345 ORDER BY created_at DESC LIMIT 50",
        "expected_answer_type": "index",
        "expected_index_hint": ["user_id", "created_at"],
        "note": "Index (user_id, created_at) giúp cả WHERE và ORDER BY",
    },
    {
        "id": "q20",
        "group": 4,
        "description": "SELECT * + ORDER BY price DESC",
        "sql": "SELECT * FROM order_items WHERE order_id = 999 ORDER BY price DESC",
        "expected_answer_type": "index",
        "expected_index_hint": ["order_id", "price"],
        "note": "Index (order_id, price DESC) hoặc (order_id, price)",
    },
    {
        "id": "q21",
        "group": 4,
        "description": "SELECT * + ORDER BY price ASC",
        "sql": "SELECT * FROM products WHERE category_id = 5 ORDER BY price ASC",
        "expected_answer_type": "index",
        "expected_index_hint": ["category_id", "price"],
        "note": "Index (category_id, price) giúp WHERE + ORDER BY",
    },
    {
        "id": "q22",
        "group": 4,
        "description": "SELECT * + ORDER BY total_amount DESC",
        "sql": "SELECT * FROM orders WHERE status = 'completed' ORDER BY total_amount DESC LIMIT 100",
        "expected_answer_type": "index",
        "expected_index_hint": ["status", "total_amount"],
        "note": "Index (status, total_amount DESC)",
    },
    {
        "id": "q23",
        "group": 4,
        "description": "SELECT * + ORDER BY created_at DESC",
        "sql": "SELECT * FROM users WHERE city = 'Hanoi' ORDER BY created_at DESC",
        "expected_answer_type": "index",
        "expected_index_hint": ["city", "created_at"],
        "note": "Index (city, created_at DESC)",
    },
    {
        "id": "q24",
        "group": 4,
        "description": "SELECT * KHÔNG WHERE → full scan + filesort toàn bảng",
        "sql": "SELECT * FROM orders ORDER BY created_at DESC LIMIT 100",
        "expected_answer_type": "index",
        "expected_index_hint": ["created_at"],
        "note": "Index (created_at DESC) → MySQL đọc 100 dòng đầu từ index, không sort",
    },

    # ============================================================
    # NHÓM 5: SUBQUERY → JOIN (6 query)
    # Bản chất: Subquery không tối ưu → rewrite thành JOIN
    # Lưu ý: MySQL 8 tự chuyển 1 số IN → semijoin, cần test thật
    # ============================================================
    {
        "id": "q25",
        "group": 5,
        "description": "IN subquery không sargable → chuyển JOIN",
        "sql": "SELECT id, email, full_name FROM users WHERE id IN (SELECT user_id FROM orders WHERE total_amount > 10000000)",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành JOIN orders ON orders.user_id = users.id WHERE orders.total_amount > 10000000, kèm DISTINCT",
    },
    {
        "id": "q26",
        "group": 5,
        "description": "NOT IN subquery → chuyển LEFT JOIN IS NULL hoặc NOT EXISTS",
        "sql": "SELECT id, email FROM users WHERE id NOT IN (SELECT user_id FROM orders WHERE status = 'cancelled')",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành LEFT JOIN orders ON ... AND status = 'cancelled' WHERE orders.id IS NULL",
    },
    {
        "id": "q27",
        "group": 5,
        "description": "EXISTS không sargable → chuyển JOIN",
        "sql": "SELECT id, email FROM users WHERE EXISTS (SELECT 1 FROM orders WHERE orders.user_id = users.id AND total_amount > 5000000)",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành JOIN orders ON orders.user_id = users.id WHERE orders.total_amount > 5000000, kèm DISTINCT",
    },
    {
        "id": "q28",
        "group": 5,
        "description": "Correlated subquery trong SELECT → chạy N lần cho N user",
        "sql": "SELECT u.id, u.email, (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS order_count FROM users u WHERE u.city = 'Hanoi'",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành LEFT JOIN orders + GROUP BY u.id, u.email",
    },
    {
        "id": "q29",
        "group": 5,
        "description": "IN subquery lồng 2 cấp → chuyển JOIN 3 bảng",
        "sql": "SELECT id, name FROM products WHERE id IN (SELECT product_id FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE status = 'completed'))",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành JOIN products + order_items + orders, kèm DISTINCT",
    },
    {
        "id": "q30",
        "group": 5,
        "description": "Subquery trong FROM → derived table, MySQL có thể không push down",
        "sql": "SELECT * FROM (SELECT user_id, COUNT(*) AS cnt FROM orders GROUP BY user_id) AS t WHERE t.cnt > 10",
        "expected_answer_type": "rewrite",
        "rewrite_hint": "Chuyển thành GROUP BY user_id HAVING COUNT(*) > 10 trực tiếp",
    },
]


# ============================================================
# HÀM HELPER
# ============================================================

def get_all_queries():
    """Lấy tất cả 30 query."""
    return QUERIES


def get_queries_by_group(group: int):
    """
    Lấy tất cả query thuộc 1 nhóm.
    
    Args:
        group: 1-5
    
    Returns:
        List các query. Rỗng nếu group không hợp lệ.
    """
    return [q for q in QUERIES if q["group"] == group]


def get_query_by_id(query_id: str):
    """
    Lấy 1 query theo id.
    
    Args:
        query_id: "q01".."q30"
    
    Returns:
        Dict query hoặc None nếu không tìm thấy.
    """
    for q in QUERIES:
        if q["id"] == query_id:
            return q
    return None


def get_queries_by_type(answer_type: str):
    """
    Lấy query theo loại đáp án.
    
    Args:
        answer_type: "index" hoặc "rewrite"
    """
    return [q for q in QUERIES if q["expected_answer_type"] == answer_type]


def get_index_queries():
    """Lấy các query cần index (nhóm 1, 2, 4) — dùng để tính Precision/Recall."""
    return [q for q in QUERIES if q["expected_answer_type"] == "index"]


def get_rewrite_queries():
    """Lấy các query cần rewrite (nhóm 3, 5) — dùng để tính metric rewrite."""
    return [q for q in QUERIES if q["expected_answer_type"] == "rewrite"]


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("KIỂM TRA 30 QUERY")
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
    index_qs = get_index_queries()
    rewrite_qs = get_rewrite_queries()
    print(f"   - Index (nhóm 1,2,4): {len(index_qs)} query")
    print(f"   - Rewrite (nhóm 3,5): {len(rewrite_qs)} query")
    
    print("\n📋 Danh sách ID:")
    ids = [q["id"] for q in QUERIES]
    print(f"   {', '.join(ids)}")
    
    print("\n" + "=" * 60)
    print("✅ HOÀN THÀNH" if len(QUERIES) == 30 else "❌ CHƯA ĐỦ 30 QUERY")
    print("=" * 60)