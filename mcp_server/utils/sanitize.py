"""
mcp_server/utils/sanitize.py
----------------------------

CHỨC NĂNG :
    Làm sạch dữ liệu lấy từ DB trước khi đưa cho LLM (chống injection gián tiếp).

PHỤ TRÁCH  : Vũ    |    REVIEW: Tình

LƯU Ý:
    - Cắt mọi comment trong SQL lấy từ slow log.
    - Lọc comment bảng/cột; gắn nhãn untrusted.
    - Chuẩn hóa Unicode để chống homoglyph.

THAM KHẢO  : project-management/ROADMAP.md (mục 2.2), tests/test_sanitize.py

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
