"""
mcp_server/validation/validator.py
----------------------------------

CHỨC NĂNG :
    Validation Layer chính: kiểm chứng đề xuất TRƯỚC khi cho người duyệt.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Quy trình: tạo index INVISIBLE -> đo 'trước' (không bật cờ) -> đo 'sau' (SET SESSION optimizer_switch='use_invisible_indexes=on') -> so sánh -> ghi validation_report.
    - Pass khi: đủ lượt đo, hash tương đương, P95 giảm >= 20%, index được EXPLAIN dùng và không lỗi/timeout.
    - Fail hoặc inconclusive: gọi helper DDL nội bộ để dọn index thử; không phát approval token.
    - Đo write overhead trên clone; ước lượng dung lượng index bằng chênh lệch TABLES.INDEX_LENGTH.
    - Ngưỡng lấy từ config/settings.yaml.

THAM KHẢO  : docs/api-contract.md (mục 4), project-management/ROADMAP.md (mục 2.3)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
