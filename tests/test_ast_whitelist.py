"""
tests/test_ast_whitelist.py
---------------------------

CHỨC NĂNG :
    Test AST whitelist: mỗi quy tắc chặn có ít nhất 1 test.

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ

LƯU Ý:
    - Cần cả test 'được phép' (SELECT hợp lệ) lẫn test 'bị chặn'.
    - Phải có test cho: multi-statement, /*!...*/, INTO OUTFILE, SLEEP, FOR UPDATE, parse lỗi.

THAM KHẢO  : security/ast_whitelist.py

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
