"""
mcp_server/store/audit_log.py
-----------------------------

CHỨC NĂNG :
    Ghi nhật ký mọi lần gọi Tool 6 (kể cả bị từ chối): thời gian, proposal_id, hash DDL, kết quả.

PHỤ TRÁCH  : Hải    |    REVIEW: Tình

LƯU Ý:
    - Chỉ ghi thêm (append-only), không sửa/xóa.
    - Không ghi token vào log.

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
