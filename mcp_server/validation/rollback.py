"""
mcp_server/validation/rollback.py
---------------------------------

CHỨC NĂNG :
    Hoàn tác thay đổi khi validation thất bại hoặc khi cần gỡ index đã áp dụng.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Rollback = DROP INDEX (hoặc chuyển lại INVISIBLE).
    - Phải chạy được cả khi validation bị ngắt giữa chừng.

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
