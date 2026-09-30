"""
mcp_server/tools/explain.py
---------------------------

CHỨC NĂNG :
    TOOL 4 — explain_query: chạy EXPLAIN FORMAT=JSON (estimate) hoặc EXPLAIN ANALYZE (analyze).

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - SQL phải qua AST whitelist trước khi chạy.
    - EXPLAIN ANALYZE CÓ chạy query thật: luôn đặt MAX_EXECUTION_TIME.
    - use_invisible_indexes chỉ dành cho Validation Layer, LLM không được đặt true.
    - Dùng readonly_user.

THAM KHẢO  : docs/api-contract.md (Tool 4)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
