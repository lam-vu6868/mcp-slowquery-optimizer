"""
data/queries/queries.py
-----------------------

CHỨC NĂNG :
    Bộ 30 câu truy vấn chậm dùng để thực nghiệm: 5 nhóm lỗi x 6 câu.

PHỤ TRÁCH  : Tường    |    REVIEW: Hải

LƯU Ý:
    - 5 nhóm: (1) thiếu index, (2) sai thứ tự cột composite, (3) hàm bọc cột / non-sargable, (4) SELECT * + filesort, (5) subquery nên chuyển thành JOIN.
    - Mỗi query có: id (q01..q30), group (1..5), sql, mô tả lỗi.
    - BẮT BUỘC xác nhận từng query chạy > 0.5s trên dữ liệu thật (MySQL 8 tự tối ưu một số subquery IN).
    - Nhóm 5: ưu tiên subquery correlated / NOT IN, tránh kiểu đã được semijoin tự động.
    - Mỗi query nên có ORDER BY xác định để hash kết quả so sánh được.

CẦN LÀM:
    [ ] Hoàn thành đủ 6 query mỗi nhóm.
    [ ] Chạy EXPLAIN gốc cho từng query và lưu lại.

THAM KHẢO  : data/queries/ground_truth.json, project-management/ROADMAP.md (mục 2.4, 2.6)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
