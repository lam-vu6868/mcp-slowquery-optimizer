"""
mcp_server/validation/hash_compare.py
-------------------------------------

CHỨC NĂNG :
    Băm tập kết quả query trước/sau để kiểm tra tính tương đương.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Cần thứ tự xác định: có ORDER BY xác định, hoặc sort mọi cột trước khi hash.
    - Chú ý NULL, kiểu số thực, và độ chính xác thập phân khi băm.

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
