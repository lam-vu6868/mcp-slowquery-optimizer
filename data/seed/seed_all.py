"""
data/seed/seed_all.py
---------------------

CHỨC NĂNG :
    Script tổng: chạy tuần tự seed toàn bộ dữ liệu thực nghiệm (users -> products -> orders -> order_items -> payments).

PHỤ TRÁCH  : Hải    |    REVIEW: Tường

LƯU Ý:
    - 12M orders + 20M order_items ước tính 2-6 giờ tùy máy, nên chạy nền/qua đêm.
    - Hỗ trợ giảm quy mô: biến môi trường SEED_SCALE=5m (đề yêu cầu tối thiểu 5 triệu bản ghi).
    - Dùng LOAD DATA INFILE (nhanh hơn INSERT nhiều lần); nên tạo index sau khi nạp xong.
    - Phân bố PHẢI lệch (Zipf cho user/product, status lệch, đỉnh Black Friday), không random đều.
    - File dữ liệu trung gian ghi vào data/generated/ (đã .gitignore), không commit.

CẦN LÀM:
    [ ] Thêm seed cho products, order_items, payments (hiện mới có seed_users, seed_orders).
    [ ] In tiến độ + tổng số dòng khi xong.

THAM KHẢO  : db/schema.sql, project-management/ROADMAP.md (mục 2.6)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
