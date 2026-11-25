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
    [x] ApprovalTokens.issue_token(proposal_id, version, ddl) -> str
    [x] ApprovalTokens.verify_token(token, proposal_id, version, ddl) -> bool
    [x] Lưu nonce đã dùng trong SQLite để chống dùng lại.
    [ ] Chỉ nối với backend/Tool 6 sau khi kiểm report và trial thật.

THAM KHẢO  : docs/api-contract.md (Tool 6), tests/test_approval_token.py

TRẠNG THÁI : ĐANG LÀM — token độc lập; chưa nối Tool 6/Dashboard.
"""

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path


class ApprovalTokens:
    """Ký token ngắn hạn và tiêu thụ nonce nguyên tử trong SQLite riêng."""

    def __init__(self, path: str | Path, *, secret: str,
                 clock: Callable[[], float] = time.time):
        if not isinstance(secret, str) or not secret:
            raise ValueError("APPROVAL_SECRET chưa được cấu hình")
        self.path = Path(path)
        self.secret = secret.encode("utf-8")
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_nonces (
                    nonce TEXT PRIMARY KEY,
                    expires_at INTEGER NOT NULL,
                    used_at INTEGER
                )
            """)
            conn.commit()

    def issue_token(self, proposal_id: str, version: int, ddl: str) -> str:
        if (not isinstance(proposal_id, str) or not proposal_id
                or type(version) is not int or version < 1
                or not isinstance(ddl, str) or not ddl):
            raise ValueError("thông tin phê duyệt không hợp lệ")
        expires_at = int(self.clock()) + 600
        nonce = secrets.token_hex(16)
        payload = {
            "proposal_id": proposal_id,
            "version": version,
            "ddl_sha256": hashlib.sha256(ddl.encode("utf-8")).hexdigest(),
            "nonce": nonce,
            "expires_at": expires_at,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self.secret, raw, hashlib.sha256).digest()
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("INSERT INTO approval_nonces (nonce, expires_at) VALUES (?, ?)",
                         (nonce, expires_at))
            conn.commit()
        return f"{_encode(raw)}.{_encode(signature)}"

    def verify_token(self, token: str, proposal_id: str, version: int, ddl: str) -> bool:
        if (not isinstance(token, str) or not 0 < len(token) <= 2048
                or not isinstance(proposal_id, str) or not isinstance(ddl, str)
                or type(version) is not int):
            return False
        try:
            encoded_payload, encoded_signature = token.split(".")
            raw = _decode(encoded_payload)
            signature = _decode(encoded_signature)
            payload = json.loads(raw)
            if not hmac.compare_digest(
                hmac.new(self.secret, raw, hashlib.sha256).digest(), signature,
            ):
                return False
            if (not isinstance(payload, dict)
                    or set(payload) != {"proposal_id", "version", "ddl_sha256",
                                            "nonce", "expires_at"}
                    or payload["proposal_id"] != proposal_id
                    or type(payload["version"]) is not int
                    or payload["version"] != version
                    or payload["ddl_sha256"] != hashlib.sha256(ddl.encode("utf-8")).hexdigest()
                    or type(payload["expires_at"]) is not int
                    or not isinstance(payload["nonce"], str)
                    or len(payload["nonce"]) != 32
                    or payload["expires_at"] <= int(self.clock())):
                return False
        except (ValueError, TypeError, UnicodeError):
            return False
        with closing(sqlite3.connect(self.path)) as conn:
            result = conn.execute(
                "UPDATE approval_nonces SET used_at=? "
                "WHERE nonce=? AND used_at IS NULL AND expires_at>?",
                (int(self.clock()), payload["nonce"], int(self.clock())),
            )
            conn.commit()
            return result.rowcount == 1


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
