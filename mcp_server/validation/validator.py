"""
mcp_server/validation/validator.py
----------------------------------

CHỨC NĂNG :
    Validation Layer chính: kiểm chứng đề xuất TRƯỚC khi cho người duyệt.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Quy trình: tạo index INVISIBLE -> đo 'trước' (không bật cờ) -> đo 'sau' (SET SESSION optimizer_switch='use_invisible_indexes=on') -> so sánh -> ghi validation_report.
    - Pass khi: kết quả tương đương (hash) VÀ P95 giảm >= 20% VÀ không lỗi/timeout.
    - Fail: DROP INDEX (rollback), đánh dấu rejected_by_validation.
    - Đo thêm write overhead (INSERT throughput) và dung lượng index.
    - Ngưỡng lấy từ config/settings.yaml.

THAM KHẢO  : docs/api-contract.md (mục 4), project-management/ROADMAP.md (mục 2.3)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
