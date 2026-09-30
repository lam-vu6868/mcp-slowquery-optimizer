"""
mcp_server/llm/agent.py
-----------------------

CHỨC NĂNG :
    Agent loop: gọi Claude, cho phép gọi Tool 1-5, thu về đề xuất cuối cùng dạng JSON.

PHỤ TRÁCH  : Vũ    |    REVIEW: Tường

LƯU Ý:
    - CHỈ nạp danh sách Tool 1-5 cho LLM (không có apply_optimization).
    - Ghim model version, temperature thấp (0-0.2) để Consistency Rate có ý nghĩa; lấy từ config/settings.yaml.
    - Ghi lại mọi lần chạy (prompt, tool call, kết quả) vào data/outputs/runs/ để tái lập.
    - Có giới hạn số lượt tool call và ngân sách token mỗi query.

CẦN LÀM:
    [ ] Vòng lặp tool-use.
    [ ] Retry khi JSON sai schema (tối đa 2 lần).

THAM KHẢO  : docs/api-contract.md (mục 2.3), config/settings.yaml

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
