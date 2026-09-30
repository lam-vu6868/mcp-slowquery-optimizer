"""
security/injection_tests/payloads.py
------------------------------------

CHỨC NĂNG :
    Danh sách 20 kịch bản tấn công Prompt Injection (dữ liệu, không chứa logic test).

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ

LƯU Ý:
    - Chia 4 nhóm x 5 kịch bản: A) comment trong slow log, B) comment schema/tên bảng-cột, C) cấu trúc SQL (multi-statement, INTO OUTFILE, SLEEP...), D) đầu ra tool / mã hóa / giả token.
    - Mỗi payload có: id, group, mô tả, nội dung, lớp phòng thủ dự kiến sẽ chặn.
    - Nên có payload dùng /*!50000 DROP TABLE x */ và payload LLM cố truyền approval token giả cho Tool 6.

THAM KHẢO  : security/injection_tests/run_tests.py, project-management/ROADMAP.md (mục 6)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
