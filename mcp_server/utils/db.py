"""
mcp_server/utils/db.py
----------------------

CHỨC NĂNG :
    Kết nối MySQL. Cung cấp 2 kết nối tách biệt: readonly_user và index_admin.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Tool 1-5 chỉ dùng kết nối readonly.
    - index_admin chỉ Tool 6 được dùng.
    - Đặt MAX_EXECUTION_TIME cho session phân tích.

THAM KHẢO  : db/init.sql

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
