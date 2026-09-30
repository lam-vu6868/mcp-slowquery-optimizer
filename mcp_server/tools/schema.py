"""
mcp_server/tools/schema.py
--------------------------

CHỨC NĂNG :
    TOOL 2 — get_schema: trả cấu trúc bảng (cột, index hiện có, khóa ngoại).

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Comment của bảng/cột là kênh injection: phải lọc và gắn untrusted.
    - Trả kèm trạng thái visible/invisible và dung lượng của từng index.
    - Dùng readonly_user.

THAM KHẢO  : docs/api-contract.md (Tool 2)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
