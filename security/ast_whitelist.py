"""
security/ast_whitelist.py
-------------------------

CHỨC NĂNG :
    AST whitelist (sqlglot, dialect mysql): kiểm mọi SQL từ bên ngoài trước khi chạy.

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ

LƯU Ý:
    - Fail-closed: parse lỗi thì TỪ CHỐI.
    - Chỉ 1 statement mỗi lần (chặn nối lệnh bằng dấu ;).
    - Chỉ cho SELECT và EXPLAIN.
    - Từ chối comment thực thi /*! ... */ và /*M! ... */.
    - Từ chối INTO OUTFILE/DUMPFILE, LOAD_FILE, FOR UPDATE, LOCK IN SHARE MODE.
    - Từ chối hàm nguy hiểm: SLEEP, BENCHMARK, GET_LOCK, RELEASE_LOCK.
    - Từ chối truy cập schema hệ thống ngoài danh sách cho phép.
    - DDL duy nhất được phép là CREATE INDEX do SERVER tự sinh ở Tool 6, không đi qua đường của LLM.
    - Mỗi quy tắc phải có ít nhất 1 test trong tests/test_ast_whitelist.py.

THAM KHẢO  : project-management/ROADMAP.md (mục 2.2), tests/test_ast_whitelist.py

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
