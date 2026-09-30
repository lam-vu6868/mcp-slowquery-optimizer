"""
mcp_server/tools/benchmark.py
-----------------------------

CHỨC NĂNG :
    TOOL 5 — benchmark_query: đo P50/P95 latency và hash kết quả.

PHỤ TRÁCH  : Tường    |    REVIEW: Hải

LƯU Ý:
    - Warm-up 3 lần (bỏ), đo >= 20 lần, ghi rõ cache_state.
    - Có timeout mỗi lần chạy.
    - Query không có ORDER BY xác định: sort kết quả trước khi hash và đặt deterministic_order=false.
    - SQL phải qua AST whitelist. Dùng readonly_user.

THAM KHẢO  : docs/api-contract.md (Tool 5), project-management/ROADMAP.md (mục 2.3)

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
