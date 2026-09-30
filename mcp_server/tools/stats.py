"""
mcp_server/tools/stats.py
-------------------------

CHỨC NĂNG :
    TOOL 3 — get_table_stats: số dòng, cardinality, phân bố giá trị từng cột.

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Dùng số ước lượng/sample, KHÔNG COUNT(*) toàn bảng mỗi lần gọi.
    - top_values chỉ trả cho cột có cardinality thấp (<= 50).
    - Dùng readonly_user.

THAM KHẢO  : docs/api-contract.md (Tool 3)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
