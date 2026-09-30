"""
data/seed/seed_orders.py
------------------------

CHỨC NĂNG :
    Sinh 12M dòng bảng orders (created_at, status, user_id, total_amount...).

PHỤ TRÁCH  : Hải    |    REVIEW: Tường

LƯU Ý:
    - status lệch (ví dụ ~85% completed), created_at có đỉnh theo mùa/Black Friday.
    - user_id theo phân bố Zipf (một số user mua rất nhiều).
    - Phải khớp cột trong db/schema.sql.

THAM KHẢO  : db/schema.sql, data/seed/seed_all.py

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
