"""
security/approval.py
--------------------

CHỨC NĂNG :
    Sinh và kiểm tra APPROVAL TOKEN cho Tool 6 (thay cho tham số approved=True).

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ + Hải (BẮT BUỘC cả hai)

LƯU Ý:
    - token = HMAC(APPROVAL_SECRET, sha256(ddl) + nonce + expires_at).
    - Hết hạn 10 phút, dùng MỘT LẦN, gắn với hash của đúng DDL đã duyệt.
    - APPROVAL_SECRET chỉ ở .env phía server; LLM không bao giờ thấy.
    - So sánh chữ ký bằng hmac.compare_digest (chống timing attack).

CẦN LÀM:
    [ ] issue_token(proposal_id, ddl) -> str
    [ ] verify_token(token, proposal_id, ddl) -> bool
    [ ] Lưu token đã dùng để chống dùng lại.

THAM KHẢO  : docs/api-contract.md (Tool 6), tests/test_approval_token.py

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
