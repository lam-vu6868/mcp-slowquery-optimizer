"""
security/approval.py
--------------------
CHỨC NĂNG:
    Sinh và kiểm tra APPROVAL TOKEN cho Tool 6 (thay cho tham số approved=True).

PHỤ TRÁCH: Tình    |    REVIEW: Vũ + Hải (BẮT BUỘC cả hai)
THAM KHẢO: docs/api-contract.md (Tool 6), docs/architecture.md (mục 5.3–5.5),
           tests/test_approval_token.py

THIẾT KẾ:
    token = "v1.<nonce>.<expires_at>.<sig>"
    sig   = HMAC-SHA256(APPROVAL_SECRET, "v1|proposal_id|sha256(ddl)|nonce|expires_at")

    - nonce 16 byte ngẫu nhiên (secrets), expires_at = UNIX time + TTL (mặc định 600s).
    - Chữ ký gắn với proposal_id VÀ hash của đúng DDL đã duyệt → đổi DDL/proposal là sai.
    - Dùng MỘT LẦN: nonce được ghi vào bảng used_tokens (PRIMARY KEY) trong SQLite meta.
      INSERT trùng → token đã dùng. Ghi nonce là thao tác nguyên tử nên 2 request song
      song không thể cùng dùng 1 token.
    - So sánh chữ ký bằng hmac.compare_digest (chống timing attack).
    - APPROVAL_SECRET chỉ ở .env phía server; LLM không bao giờ thấy. Secret rỗng,
      còn giá trị mẫu, hoặc < 32 ký tự → TỪ CHỐI cả sinh lẫn kiểm (fail-closed).
    - Không log token. Chỉ log proposal_id + ddl_hash (xem store/audit_log.py).
"""
import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# Nạp .env (Config gọi load_dotenv khi import)
from mcp_server.utils import config as _config  # noqa: F401
from mcp_server.store.meta_db import get_meta_conn

TOKEN_VERSION = "v1"
DEFAULT_TTL_SECONDS = 600
MIN_SECRET_LENGTH = 32
_PLACEHOLDER_PREFIX = "CHANGE_ME"


class ApprovalConfigError(RuntimeError):
    """Secret chưa cấu hình đúng → hệ thống từ chối duyệt (fail-closed)."""


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at: int
    ddl_hash: str


@dataclass(frozen=True)
class TokenCheck:
    ok: bool
    reason: str          # mã lý do ngắn: OK, MISSING, MALFORMED, BAD_SIGNATURE, EXPIRED, REUSED, NO_SECRET
    message: str = ""

    def __bool__(self) -> bool:  # cho phép dùng `if verify_token(...)`
        return self.ok


# ============================================================
# HELPERS
# ============================================================

def ddl_hash(ddl: str) -> str:
    """sha256 của DDL đã chuẩn hóa khoảng trắng (để log và ký)."""
    normalized = " ".join((ddl or "").split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _get_secret() -> bytes:
    secret = os.getenv("APPROVAL_SECRET", "")
    if not secret or secret.startswith(_PLACEHOLDER_PREFIX) or len(secret) < MIN_SECRET_LENGTH:
        raise ApprovalConfigError(
            "APPROVAL_SECRET chưa cấu hình (rỗng, còn giá trị mẫu hoặc < 32 ký tự). "
            'Tạo bằng: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return secret.encode("utf-8")


def _ttl() -> int:
    try:
        ttl = int(os.getenv("APPROVAL_TOKEN_TTL", DEFAULT_TTL_SECONDS))
    except ValueError:
        ttl = DEFAULT_TTL_SECONDS
    # Không cho cấu hình TTL vô lý
    return max(30, min(ttl, 3600))


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _sign(secret: bytes, proposal_id: str, dhash: str, nonce: str, expires_at: int) -> str:
    msg = f"{TOKEN_VERSION}|{proposal_id}|{dhash}|{nonce}|{expires_at}".encode("utf-8")
    return _b64(hmac.new(secret, msg, hashlib.sha256).digest())


def is_configured() -> bool:
    """Dashboard dùng để hiển thị trạng thái hệ thống."""
    try:
        _get_secret()
        return True
    except ApprovalConfigError:
        return False


# ============================================================
# API CHÍNH
# ============================================================

def issue_token(proposal_id: str, ddl: str, now: Optional[float] = None) -> IssuedToken:
    """
    Sinh token cho đúng (proposal_id, ddl). Chỉ backend Dashboard gọi, SAU KHI người bấm Approve.
    """
    if not proposal_id or not ddl:
        raise ValueError("proposal_id và ddl không được rỗng")
    secret = _get_secret()
    now = time.time() if now is None else now
    expires_at = int(now) + _ttl()
    nonce = secrets.token_hex(16)
    dhash = ddl_hash(ddl)
    sig = _sign(secret, proposal_id, dhash, nonce, expires_at)
    return IssuedToken(
        token=f"{TOKEN_VERSION}.{nonce}.{expires_at}.{sig}",
        expires_at=expires_at,
        ddl_hash=dhash,
    )


def verify_token(
    token: Optional[str],
    proposal_id: str,
    ddl: str,
    consume: bool = True,
    now: Optional[float] = None,
) -> TokenCheck:
    """
    Kiểm tra token. Thứ tự: định dạng → chữ ký → hạn → chưa dùng (và đánh dấu đã dùng).

    consume=True (mặc định, Tool 6 dùng): token hợp lệ sẽ bị "đốt" ngay, không dùng lại được.
    """
    if not token or not isinstance(token, str):
        return TokenCheck(False, "MISSING", "Thiếu approval token")

    try:
        secret = _get_secret()
    except ApprovalConfigError as e:
        return TokenCheck(False, "NO_SECRET", str(e))

    parts = token.strip().split(".")
    if len(parts) != 4 or parts[0] != TOKEN_VERSION:
        return TokenCheck(False, "MALFORMED", "Token sai định dạng")
    _, nonce, exp_str, sig = parts
    if len(nonce) != 32 or not all(c in "0123456789abcdef" for c in nonce):
        return TokenCheck(False, "MALFORMED", "Nonce sai định dạng")
    if not exp_str.isdigit():
        return TokenCheck(False, "MALFORMED", "expires_at sai định dạng")
    expires_at = int(exp_str)

    expected = _sign(secret, proposal_id, ddl_hash(ddl), nonce, expires_at)
    if not hmac.compare_digest(expected, sig):
        # Sai secret, bị sửa, khác proposal_id hoặc khác DDL đều rơi vào đây
        return TokenCheck(False, "BAD_SIGNATURE", "Chữ ký không khớp (token giả, bị sửa, hoặc khác proposal/DDL)")

    now = time.time() if now is None else now
    if now > expires_at:
        return TokenCheck(False, "EXPIRED", "Token đã hết hạn")

    if consume:
        try:
            with get_meta_conn() as conn:
                conn.execute(
                    "INSERT INTO used_tokens (nonce, proposal_id, used_at) VALUES (?, ?, ?)",
                    (nonce, proposal_id,
                     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
                )
        except sqlite3.IntegrityError:
            return TokenCheck(False, "REUSED", "Token đã được sử dụng")
    else:
        with get_meta_conn() as conn:
            used = conn.execute(
                "SELECT 1 FROM used_tokens WHERE nonce = ?", (nonce,)
            ).fetchone()
        if used:
            return TokenCheck(False, "REUSED", "Token đã được sử dụng")

    return TokenCheck(True, "OK", "Token hợp lệ")
