"""
Ứng viên kiểm chứng cho bộ 5 bảng, không phải đáp án đã được chấp nhận.
PHỤ TRÁCH: Tường | REVIEW: Hải.
LƯU Ý: chỉ scripts/verify_ground_truth.py dùng để thử INVISIBLE INDEX trong lab.
THAM KHẢO: queries.py, ground_truth.json, docs/api-contract.md.
"""
from data.queries.queries import get_query_by_id

CANDIDATES = {
    "q02": {"indexes": [("orders", ["customer_id", "order_date", "total_amount"])], "force_indexes": True},
    "q03": {"indexes": [("order_items", ["product_id", "quantity"])]},
    "q04": {
        "indexes": [("order_items", ["order_id", "product_id", "quantity", "unit_price"])],
        "force_indexes": True,
        "rewritten_sql": "SELECT p.category, SUM(s.revenue) AS revenue FROM products p JOIN (SELECT i.product_id, SUM(i.quantity*i.unit_price) AS revenue FROM orders o JOIN order_items i ON i.order_id=o.order_id WHERE o.total_amount>100000 GROUP BY i.product_id) s ON s.product_id=p.product_id GROUP BY p.category",
    },
    "q05": {"indexes": [("order_items", ["unit_price", "product_id", "quantity"])]},
    "q06": {"indexes": [("orders", ["order_date", "customer_id", "total_amount"]), ("addresses", ["customer_id", "city"])], "force_indexes": True},
    "q07": {
        "force_indexes": True,
        "indexes": [("orders", ["status", "order_date", "customer_id", "total_amount"]), ("addresses", ["customer_id", "city"])],
        "wrong_indexes": [("orders", ["order_date", "status", "customer_id", "total_amount"]), ("addresses", ["customer_id", "city"])],
    },
    "q08": {
        "force_indexes": True,
        "indexes": [("order_items", ["order_id", "product_id", "quantity", "unit_price"])],
        "wrong_indexes": [("order_items", ["product_id", "order_id", "quantity", "unit_price"])],
        "rewritten_sql": "SELECT p.category, SUM(s.revenue) AS revenue FROM products p JOIN (SELECT i.product_id, SUM(i.quantity*i.unit_price) AS revenue FROM orders o JOIN order_items i ON i.order_id=o.order_id WHERE o.status='completed' AND o.total_amount>10000 GROUP BY i.product_id) s ON s.product_id=p.product_id GROUP BY p.category",
    },
    "q09": {
        "indexes": [("order_items", ["quantity", "unit_price", "product_id"])],
        "wrong_indexes": [("order_items", ["unit_price", "quantity", "product_id"])],
    },
    "q10": {
        "force_indexes": True,
        "indexes": [("order_items", ["product_id", "order_id", "quantity"])],
        "wrong_indexes": [("order_items", ["order_id", "product_id", "quantity"])],
    },
    "q11": {
        "force_indexes": True,
        "indexes": [("orders", ["customer_id", "status", "total_amount"])],
        "wrong_indexes": [("orders", ["status", "customer_id", "total_amount"])],
    },
    "q12": {
        "force_indexes": True,
        "indexes": [("order_items", ["order_id", "product_id", "quantity", "unit_price"])],
        "wrong_indexes": [("order_items", ["product_id", "order_id", "quantity", "unit_price"])],
        "rewritten_sql": "SELECT p.category, SUM(s.revenue) AS revenue FROM products p JOIN (SELECT i.product_id, SUM(i.quantity*i.unit_price) AS revenue FROM orders o JOIN order_items i ON i.order_id=o.order_id WHERE o.status='shipped' AND o.order_date>='2023-06-01' AND o.order_date<'2025-01-01' GROUP BY i.product_id) s ON s.product_id=p.product_id GROUP BY p.category",
    },
    "q13": {
        "force_indexes": True,
        "indexes": [("orders", ["order_date"]), ("order_items", ["order_id", "product_id", "quantity", "unit_price"])],
        "rewritten_sql": get_query_by_id("q13")["sql"].replace("YEAR(o.order_date)=2024", "o.order_date>='2024-01-01' AND o.order_date<'2025-01-01'"),
    },
    "q14": {
        "indexes": [("orders", ["order_date", "customer_id", "total_amount"])],
        "rewritten_sql": get_query_by_id("q14")["sql"].replace("DATE_FORMAT(o.order_date,'%Y-%m')='2024-11'", "o.order_date>='2024-11-01' AND o.order_date<'2024-12-01'"),
    },
    "q15": {
        "force_indexes": True,
        "indexes": [("orders", ["order_date"]), ("order_items", ["order_id", "product_id", "quantity"])],
        "rewritten_sql": get_query_by_id("q15")["sql"].replace("DATE(o.order_date)>='2024-01-01' AND DATE(o.order_date)<='2024-12-31'", "o.order_date>='2024-01-01' AND o.order_date<'2025-01-01'"),
    },
    "q16": {
        "indexes": [("orders", ["status"]), ("order_items", ["order_id", "product_id", "quantity", "unit_price"])],
        "rewritten_sql": get_query_by_id("q16")["sql"].replace("UPPER(o.status)='COMPLETED'", "o.status='completed'"),
    },
    "q17": {
        "indexes": [("order_items", ["product_id", "quantity", "unit_price"])],
        "rewritten_sql": "SELECT p.category, SUM(s.revenue) AS revenue FROM products p JOIN (SELECT product_id, SUM(quantity*unit_price) AS revenue FROM order_items WHERE unit_price>4900 GROUP BY product_id) s ON s.product_id=p.product_id GROUP BY p.category",
    },
    "q18": {
        "indexes": [("order_items", ["product_id", "order_id", "quantity", "unit_price"])],
        "rewritten_sql": get_query_by_id("q18")["sql"].replace("LEFT(p.category,4)='Dien'", "p.category LIKE 'Dien%'"),
    },
    "q19": {"indexes": [("orders", ["status", "order_date DESC", "order_id DESC", "customer_id", "total_amount"])], "force_indexes": True, "straight_join": True},
    "q20": {"indexes": [("order_items", ["unit_price DESC", "order_item_id DESC", "product_id", "order_id", "quantity"])], "force_indexes": True, "straight_join": True},
    "q21": {"indexes": [("orders", ["total_amount DESC", "order_id DESC", "customer_id", "order_date", "status"])], "force_indexes": True, "straight_join": True},
    "q22": {"indexes": [("order_items", ["quantity DESC", "unit_price DESC", "order_item_id DESC", "order_id", "product_id"])], "force_indexes": True, "straight_join": True},
    "q23": {"indexes": [("order_items", ["unit_price DESC", "quantity DESC", "order_item_id DESC", "product_id", "order_id"])], "force_indexes": True, "straight_join": True},
    "q24": {
        "force_indexes": True,
        "straight_join": True,
        "indexes": [("orders", ["order_date DESC", "total_amount DESC", "order_id DESC", "customer_id", "status"])],
        "rewritten_sql": get_query_by_id("q24")["sql"].replace(", i.order_item_id DESC", ""),
        "note": "Bỏ khóa phụ i.order_item_id: các dòng cùng o.order_id có o.* giống hệt nhau, giữ nguyên thứ tự giá trị và số lần lặp của kết quả.",
    },
    "q25": {
        "indexes": [("orders", ["customer_id", "total_amount", "status"])],
        "rewritten_sql": "SELECT o.status, COUNT(*) AS n FROM orders o JOIN (SELECT customer_id, AVG(total_amount) AS avg_amount FROM orders GROUP BY customer_id) s ON s.customer_id=o.customer_id WHERE o.total_amount>s.avg_amount GROUP BY o.status",
    },
    "q26": {
        "force_indexes": True,
        "indexes": [("order_items", ["order_id", "product_id", "quantity"]), ("orders", ["status"])],
        "rewritten_sql": "SELECT p.category, SUM(i.quantity) AS sold FROM order_items i JOIN products p ON p.product_id=i.product_id JOIN orders o ON o.order_id=i.order_id WHERE o.status='paid' GROUP BY p.category",
    },
    "q27": {
        "force_indexes": True,
        "indexes": [("order_items", ["order_id", "quantity"])],
        "rewritten_sql": "SELECT o.status, COUNT(*) AS n FROM orders o LEFT JOIN order_items i ON i.order_id=o.order_id AND i.quantity=4 WHERE i.order_item_id IS NULL GROUP BY o.status",
    },
    "q28": {
        "indexes": [("orders", ["status", "customer_id"])],
        "rewritten_sql": "SELECT a.city, COUNT(*) AS n FROM customers c JOIN addresses a ON a.customer_id=c.customer_id JOIN (SELECT DISTINCT customer_id FROM orders WHERE status='completed') s ON s.customer_id=c.customer_id GROUP BY a.city",
    },
    "q29": {
        "indexes": [("order_items", ["product_id", "order_id"])],
        "rewritten_sql": "SELECT o.status, COUNT(*) AS n FROM orders o JOIN (SELECT DISTINCT i.order_id FROM order_items i JOIN products p ON p.product_id=i.product_id WHERE p.category='Dien tu') s ON s.order_id=o.order_id GROUP BY o.status",
    },
    "q30": {
        "force_indexes": True,
        "straight_join": True,
        "indexes": [("addresses", ["city", "customer_id"]), ("orders", ["customer_id", "status"]), ("order_items", ["order_id", "unit_price"])],
        "rewritten_sql": "SELECT o.status, COUNT(*) AS n FROM (SELECT DISTINCT customer_id FROM addresses WHERE city='Ha Noi') a JOIN orders o ON o.customer_id=a.customer_id JOIN LATERAL (SELECT 1 AS found FROM order_items i WHERE i.order_id=o.order_id AND i.unit_price>5000 LIMIT 1) hit ON TRUE GROUP BY o.status",
        "note": "MySQL >=8.0.14: JOIN LATERAL lấy tối đa một dòng hàng khớp cho mỗi đơn, DISTINCT customer_id tránh nhân bản vì nhiều địa chỉ; giữ ngữ nghĩa IN khi có NULL/trùng. Phải dùng đầy đủ SQL và các index kèm theo.",
    },
}
