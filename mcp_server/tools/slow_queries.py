"""
mcp_server/tools/slow_queries.py
--------------------------------

CHỨC NĂNG :
    TOOL 1 — get_slow_queries: trả top N query chậm (digest, latency, rows examined).

PHỤ TRÁCH  : Vũ    |    REVIEW: Hải

LƯU Ý:
    - Nguồn chính: performance_schema.events_statements_summary_by_digest; phụ: mysql.slow_log.
    - Strip comment khỏi SQL trước khi trả (chống injection qua slow log) và gắn untrusted=true.
    - Tối đa 100 dòng, có cờ truncated.
    - Dùng readonly_user.

THAM KHẢO  : docs/api-contract.md (Tool 1)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
