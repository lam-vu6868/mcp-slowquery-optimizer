"""
dashboard/app.py
----------------

CHỨC NĂNG :
    Điểm vào (entry point) của Dashboard Streamlit: trang chủ + cấu hình chung. 4 tab nằm trong thư mục pages/.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Chạy: streamlit run dashboard/app.py
    - Phải có try/except khi chưa có dữ liệu (trước đây từng crash).
    - Dashboard KHÔNG tự chạy DDL: chỉ gọi Tool 6 kèm approval token sau khi người bấm Approve.

CẦN LÀM:
    [ ] Trang chủ: tổng quan (số query chậm, số đề xuất chờ duyệt, trạng thái hệ thống).

THAM KHẢO  : docs/api-contract.md, dashboard/pages/

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
