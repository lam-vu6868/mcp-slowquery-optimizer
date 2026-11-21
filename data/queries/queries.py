"""
30 query chậm — Tường phụ trách.
Dataset: shopdb — customers, addresses, products, orders, order_items (tổng 5M dòng).
Đã sàng lọc trên MySQL: 1 warm-up + 3 lượt đo phía server đều >= 500 ms.
Chưa đo P95 chính thức hoặc kiểm chứng đáp án tối ưu.
Người làm: Tường
Reviewer: Hải

Nhóm 1: Thiếu index (q01-q06)
Nhóm 2: Ứng viên composite (q07-q12), chưa dựng index sai thứ tự.
Nhóm 3: Hàm bọc cột - non-sargable (q13-q18)
Nhóm 4: SELECT * + filesort (q19-q24)
Nhóm 5: Subquery → JOIN giữa các bảng (q25-q30)
"""

QUERIES = [
    {
        "id": "q01",
        "group": 1,
        "description": "Doanh thu theo nhóm sản phẩm, thiếu lọc category",
        "sql": "SELECT p.category, SUM(i.quantity*i.unit_price) AS revenue FROM products p JOIN order_items i ON i.product_id=p.product_id WHERE p.category='Dien tu' GROUP BY p.category",
        "expected_answer_type": "index"
    },
    {
        "id": "q02",
        "group": 1,
        "description": "Doanh thu theo tháng của khách ở Hà Nội",
        "sql": "SELECT YEAR(o.order_date) AS y, MONTH(o.order_date) AS m, SUM(o.total_amount) AS revenue FROM orders o JOIN addresses a ON a.customer_id=o.customer_id WHERE a.city='Ha Noi' GROUP BY YEAR(o.order_date), MONTH(o.order_date)",
        "expected_answer_type": "index"
    },
    {
        "id": "q03",
        "group": 1,
        "description": "Số lượng bán theo nhóm sản phẩm sắp hết tồn kho",
        "sql": "SELECT p.category, SUM(i.quantity) AS sold FROM products p JOIN order_items i ON i.product_id=p.product_id WHERE p.stock_quantity<100 GROUP BY p.category",
        "expected_answer_type": "index"
    },
    {
        "id": "q04",
        "group": 1,
        "description": "Sản phẩm thuộc các đơn hàng giá trị cao",
        "sql": "SELECT p.category, SUM(i.quantity*i.unit_price) AS revenue FROM orders o JOIN order_items i ON i.order_id=o.order_id JOIN products p ON p.product_id=i.product_id WHERE o.total_amount>100000 GROUP BY p.category",
        "expected_answer_type": "index"
    },
    {
        "id": "q05",
        "group": 1,
        "description": "Doanh thu theo nhóm ở một khoảng đơn giá",
        "sql": "SELECT p.category, SUM(i.quantity*i.unit_price) AS revenue FROM order_items i JOIN products p ON p.product_id=i.product_id WHERE i.unit_price BETWEEN 1000 AND 20000 GROUP BY p.category",
        "expected_answer_type": "index"
    },
    {
        "id": "q06",
        "group": 1,
        "description": "Doanh thu năm 2024 theo thành phố",
        "sql": "SELECT a.city, SUM(o.total_amount) AS revenue FROM orders o JOIN addresses a ON a.customer_id=o.customer_id WHERE o.order_date>='2024-01-01' AND o.order_date<'2025-01-01' GROUP BY a.city",
        "expected_answer_type": "index"
    },
    {
        "id": "q07",
        "group": 2,
        "description": "Composite status equality + order_date range",
        "sql": "SELECT a.city, SUM(o.total_amount) AS revenue FROM orders o JOIN addresses a ON a.customer_id=o.customer_id WHERE o.status='paid' AND o.order_date>='2024-01-01' AND o.order_date<'2025-01-01' GROUP BY a.city",
        "expected_answer_type": "index",
        "note": "Đã sàng lọc latency; chưa tạo index sai thứ tự hoặc kiểm chứng thứ tự composite tối ưu."
    },
    {
        "id": "q08",
        "group": 2,
        "description": "Composite status equality + total_amount range",
        "sql": "SELECT p.category, SUM(i.quantity*i.unit_price) AS revenue FROM orders o JOIN order_items i ON i.order_id=o.order_id JOIN products p ON p.product_id=i.product_id WHERE o.status='completed' AND o.total_amount>10000 GROUP BY p.category",
        "expected_answer_type": "index",
        "note": "Đã sàng lọc latency; chưa tạo index sai thứ tự hoặc kiểm chứng thứ tự composite tối ưu."
    },
    {
        "id": "q09",
        "group": 2,
        "description": "Composite quantity equality + unit_price range",
        "sql": "SELECT p.category, SUM(i.quantity*i.unit_price) AS revenue FROM order_items i JOIN products p ON p.product_id=i.product_id WHERE i.quantity=4 AND i.unit_price>1000 GROUP BY p.category",
        "expected_answer_type": "index",
        "note": "Đã sàng lọc latency; chưa tạo index sai thứ tự hoặc kiểm chứng thứ tự composite tối ưu."
    },
    {
        "id": "q10",
        "group": 2,
        "description": "Composite category equality + price range",
        "sql": "SELECT o.status, SUM(i.quantity) AS sold FROM products p JOIN order_items i ON i.product_id=p.product_id JOIN orders o ON o.order_id=i.order_id WHERE p.category='Sach' AND p.price>1000 GROUP BY o.status",
        "expected_answer_type": "index",
        "note": "Đã sàng lọc latency; chưa tạo index sai thứ tự hoặc kiểm chứng thứ tự composite tối ưu."
    },
    {
        "id": "q11",
        "group": 2,
        "description": "Composite city equality + address_id range",
        "sql": "SELECT o.status, SUM(o.total_amount) AS revenue FROM addresses a JOIN orders o ON o.customer_id=a.customer_id WHERE a.city='Ho Chi Minh' AND a.address_id>100000 GROUP BY o.status",
        "expected_answer_type": "index",
        "note": "Đã sàng lọc latency; chưa tạo index sai thứ tự hoặc kiểm chứng thứ tự composite tối ưu."
    },
    {
        "id": "q12",
        "group": 2,
        "description": "Composite status equality + order_date range, doanh thu sản phẩm",
        "sql": "SELECT p.category, SUM(i.quantity*i.unit_price) AS revenue FROM orders o JOIN order_items i ON i.order_id=o.order_id JOIN products p ON p.product_id=i.product_id WHERE o.status='shipped' AND o.order_date>='2023-06-01' AND o.order_date<'2025-01-01' GROUP BY p.category",
        "expected_answer_type": "index",
        "note": "Đã sàng lọc latency; chưa tạo index sai thứ tự hoặc kiểm chứng thứ tự composite tối ưu."
    },
    {
        "id": "q13",
        "group": 3,
        "description": "YEAR bọc order_date",
        "sql": "SELECT p.category, SUM(i.quantity*i.unit_price) AS revenue FROM orders o JOIN order_items i ON i.order_id=o.order_id JOIN products p ON p.product_id=i.product_id WHERE YEAR(o.order_date)=2024 GROUP BY p.category",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q14",
        "group": 3,
        "description": "DATE_FORMAT bọc order_date",
        "sql": "SELECT a.city, SUM(o.total_amount) AS revenue FROM orders o JOIN addresses a ON a.customer_id=o.customer_id WHERE DATE_FORMAT(o.order_date,'%Y-%m')='2024-11' GROUP BY a.city",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q15",
        "group": 3,
        "description": "DATE bọc TIMESTAMP, phải rewrite bằng khoảng thời gian",
        "sql": "SELECT p.category, SUM(i.quantity) AS sold FROM orders o JOIN order_items i ON i.order_id=o.order_id JOIN products p ON p.product_id=i.product_id WHERE DATE(o.order_date)>='2024-01-01' AND DATE(o.order_date)<='2024-12-31' GROUP BY p.category",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q16",
        "group": 3,
        "description": "UPPER bọc status trong collation không phân biệt hoa thường",
        "sql": "SELECT p.category, SUM(i.quantity*i.unit_price) AS revenue FROM orders o JOIN order_items i ON i.order_id=o.order_id JOIN products p ON p.product_id=i.product_id WHERE UPPER(o.status)='COMPLETED' GROUP BY p.category",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q17",
        "group": 3,
        "description": "Phép cộng trên cột unit_price",
        "sql": "SELECT p.category, SUM(i.quantity*i.unit_price) AS revenue FROM order_items i JOIN products p ON p.product_id=i.product_id WHERE i.unit_price+100>5000 GROUP BY p.category",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q18",
        "group": 3,
        "description": "LEFT bọc category",
        "sql": "SELECT o.status, SUM(i.quantity*i.unit_price) AS revenue FROM products p JOIN order_items i ON i.product_id=p.product_id JOIN orders o ON o.order_id=i.order_id WHERE LEFT(p.category,4)='Dien' GROUP BY o.status",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q19",
        "group": 4,
        "description": "SELECT o.* lọc status và filesort theo ngày",
        "sql": "SELECT o.* FROM orders o JOIN addresses a ON a.customer_id=o.customer_id WHERE o.status='paid' AND a.city='Ho Chi Minh' ORDER BY o.order_date DESC, o.order_id DESC LIMIT 1000",
        "expected_answer_type": "index"
    },
    {
        "id": "q20",
        "group": 4,
        "description": "SELECT i.* theo category, filesort đơn giá",
        "sql": "SELECT i.* FROM order_items i JOIN products p ON p.product_id=i.product_id WHERE p.category='Dien tu' ORDER BY i.unit_price DESC, i.order_item_id DESC LIMIT 1000",
        "expected_answer_type": "index"
    },
    {
        "id": "q21",
        "group": 4,
        "description": "SELECT o.* theo thành phố, filesort tổng tiền",
        "sql": "SELECT o.* FROM orders o JOIN addresses a ON a.customer_id=o.customer_id WHERE a.city='Da Nang' ORDER BY o.total_amount DESC, o.order_id DESC LIMIT 1000",
        "expected_answer_type": "index"
    },
    {
        "id": "q22",
        "group": 4,
        "description": "SELECT i.* theo status, filesort số lượng và giá",
        "sql": "SELECT i.* FROM order_items i JOIN orders o ON o.order_id=i.order_id WHERE o.status='completed' ORDER BY i.quantity DESC, i.unit_price DESC, i.order_item_id DESC LIMIT 1000",
        "expected_answer_type": "index"
    },
    {
        "id": "q23",
        "group": 4,
        "description": "SELECT i.* theo category, filesort đơn giá và số lượng",
        "sql": "SELECT i.* FROM order_items i JOIN products p ON p.product_id=i.product_id WHERE p.category='Thoi trang' ORDER BY i.unit_price DESC, i.quantity DESC, i.order_item_id DESC LIMIT 1000",
        "expected_answer_type": "index"
    },
    {
        "id": "q24",
        "group": 4,
        "description": "SELECT o.* cho sản phẩm, filesort ngày và tổng tiền",
        "sql": "SELECT o.* FROM orders o JOIN order_items i ON i.order_id=o.order_id JOIN products p ON p.product_id=i.product_id WHERE p.category='The thao' ORDER BY o.order_date DESC, o.total_amount DESC, o.order_id DESC, i.order_item_id DESC LIMIT 1000",
        "expected_answer_type": "index"
    },
    {
        "id": "q25",
        "group": 5,
        "description": "Correlated AVG đơn hàng theo khách → JOIN bảng tổng hợp",
        "sql": "SELECT o.status, COUNT(*) AS n FROM orders o WHERE o.total_amount>(SELECT AVG(o2.total_amount) FROM orders o2 WHERE o2.customer_id=o.customer_id) GROUP BY o.status",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q26",
        "group": 5,
        "description": "IN đơn đã thanh toán → JOIN orders",
        "sql": "SELECT p.category, SUM(i.quantity) AS sold FROM order_items i JOIN products p ON p.product_id=i.product_id WHERE i.order_id IN (SELECT o.order_id FROM orders o WHERE o.status='paid') GROUP BY p.category",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q27",
        "group": 5,
        "description": "NOT EXISTS mặt hàng số lượng lớn → LEFT JOIN IS NULL",
        "sql": "SELECT o.status, COUNT(*) AS n FROM orders o WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id=o.order_id AND i.quantity=4) GROUP BY o.status",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q28",
        "group": 5,
        "description": "Correlated COUNT đơn hoàn tất → JOIN tập khách DISTINCT",
        "sql": "SELECT a.city, COUNT(*) AS n FROM customers c JOIN addresses a ON a.customer_id=c.customer_id WHERE (SELECT COUNT(*) FROM orders o WHERE o.customer_id=c.customer_id AND o.status='completed')>0 GROUP BY a.city",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q29",
        "group": 5,
        "description": "EXISTS mặt hàng điện tử → JOIN tập order_id DISTINCT",
        "sql": "SELECT o.status, COUNT(*) AS n FROM orders o WHERE EXISTS (SELECT 1 FROM order_items i JOIN products p ON p.product_id=i.product_id WHERE i.order_id=o.order_id AND p.category='Dien tu') GROUP BY o.status",
        "expected_answer_type": "rewrite"
    },
    {
        "id": "q30",
        "group": 5,
        "description": "Hai IN subquery địa chỉ và mặt hàng → JOIN tập DISTINCT",
        "sql": "SELECT o.status, COUNT(*) AS n FROM orders o WHERE o.customer_id IN (SELECT a.customer_id FROM addresses a WHERE a.city='Ha Noi') AND o.order_id IN (SELECT i.order_id FROM order_items i WHERE i.unit_price>5000) GROUP BY o.status",
        "expected_answer_type": "rewrite"
    }
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
    print("KIỂM TRA 30 QUERY — SHOPDB 5 BẢNG")
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
