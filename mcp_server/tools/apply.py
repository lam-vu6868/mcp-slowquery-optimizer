"""
mcp_server/tools/apply.py
-------------------------

CHỨC NĂNG :
    TOOL 6 — apply_optimization: áp dụng THẬT một đề xuất index đã được người duyệt.

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ + Hải (BẮT BUỘC cả hai)

LƯU Ý:
    - KHÔNG được cấp cho LLM. Chỉ backend Dashboard gọi.
    - Input CHỈ gồm proposal_id + approval_token. TUYỆT ĐỐI không nhận SQL tự do.
    - Kiểm token: đúng chữ ký, chưa hết hạn, chưa dùng, khớp proposal ID/version và hash DDL ALTER INDEX VISIBLE thực tế.
    - Proposal loại 'rewrite' luôn bị từ chối (FORBIDDEN).
    - Chỉ cho apply khi validation_report.status == 'passed' và đủ bằng chứng đo.
    - Dùng tài khoản index_admin (chỉ CREATE/DROP INDEX, ALTER INDEX).
    - Helper DDL nội bộ trong file này phục vụ Validation tạo/dọn index INVISIBLE; không công bố thành MCP tool.
    - Mọi lần gọi (kể cả bị từ chối) đều ghi audit_log.

THAM KHẢO  : docs/api-contract.md (Tool 6), security/approval.py

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
