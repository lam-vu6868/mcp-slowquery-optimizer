"""
tests/test_approval_token.py
----------------------------
CHỨC NĂNG: Test approval token: sai chữ ký, hết hạn, dùng lại, khác DDL, thiếu token, thiếu secret.
PHỤ TRÁCH: Tình    |    REVIEW: Vũ
THAM KHẢO: security/approval.py
"""
import sqlite3
import time

import pytest

from security import approval

DDL = "CREATE INDEX `idx_sales_region` ON `sales_data` (`region`)"
PID = "p_20261106_abc123"


class TestIssueAndVerify:
    def test_valid_token_passes(self, security_env):
        t = approval.issue_token(PID, DDL)
        chk = approval.verify_token(t.token, PID, DDL)
        assert chk.ok and chk.reason == "OK"

    def test_token_format(self, security_env):
        t = approval.issue_token(PID, DDL)
        parts = t.token.split(".")
        assert parts[0] == "v1" and len(parts) == 4 and len(parts[1]) == 32
        assert t.ddl_hash.startswith("sha256:")

    def test_ttl_is_10_minutes(self, security_env):
        now = 1_800_000_000
        t = approval.issue_token(PID, DDL, now=now)
        assert t.expires_at == now + 600

    def test_whitespace_in_ddl_does_not_matter(self, security_env):
        t = approval.issue_token(PID, DDL)
        assert approval.verify_token(t.token, PID, "  " + DDL.replace(" ", "   ") + " ").ok


class TestRejections:
    @pytest.mark.parametrize("bad", [None, "", "   "])
    def test_missing_token(self, security_env, bad):
        chk = approval.verify_token(bad, PID, DDL)
        assert not chk.ok and chk.reason in ("MISSING", "MALFORMED")

    @pytest.mark.parametrize("bad", [
        "approved", "true", "v1.abc", "v2.%s.123.sig" % ("a" * 32),
        "v1.%s.notanumber.sig" % ("a" * 32), "v1.ZZZ.123.sig",
    ])
    def test_malformed(self, security_env, bad):
        assert approval.verify_token(bad, PID, DDL).reason == "MALFORMED"

    def test_tampered_signature(self, security_env):
        t = approval.issue_token(PID, DDL).token
        tampered = t[:-2] + ("AA" if not t.endswith("AA") else "BB")
        assert approval.verify_token(tampered, PID, DDL).reason == "BAD_SIGNATURE"

    def test_tampered_expiry(self, security_env):
        v, nonce, exp, sig = approval.issue_token(PID, DDL).token.split(".")
        forged = ".".join([v, nonce, str(int(exp) + 99999), sig])
        assert approval.verify_token(forged, PID, DDL).reason == "BAD_SIGNATURE"

    def test_different_ddl(self, security_env):
        t = approval.issue_token(PID, DDL).token
        other = "CREATE INDEX `idx_sales_region` ON `sales_data` (`region`, `country`)"
        assert approval.verify_token(t, PID, other).reason == "BAD_SIGNATURE"

    def test_different_proposal(self, security_env):
        t = approval.issue_token(PID, DDL).token
        assert approval.verify_token(t, "p_20261106_zzz999", DDL).reason == "BAD_SIGNATURE"

    def test_wrong_secret(self, security_env, monkeypatch):
        t = approval.issue_token(PID, DDL).token
        monkeypatch.setenv("APPROVAL_SECRET", "another_secret_" + "b" * 40)
        assert approval.verify_token(t, PID, DDL).reason == "BAD_SIGNATURE"

    def test_expired(self, security_env):
        now = time.time()
        t = approval.issue_token(PID, DDL, now=now - 601).token
        assert approval.verify_token(t, PID, DDL, now=now).reason == "EXPIRED"

    def test_reuse_rejected(self, security_env):
        t = approval.issue_token(PID, DDL).token
        assert approval.verify_token(t, PID, DDL).ok
        assert approval.verify_token(t, PID, DDL).reason == "REUSED"

    def test_peek_does_not_consume(self, security_env):
        t = approval.issue_token(PID, DDL).token
        assert approval.verify_token(t, PID, DDL, consume=False).ok
        assert approval.verify_token(t, PID, DDL).ok
        assert approval.verify_token(t, PID, DDL, consume=False).reason == "REUSED"

    def test_failed_check_does_not_burn_token(self, security_env):
        t = approval.issue_token(PID, DDL).token
        assert not approval.verify_token(t, "p_other_1", DDL).ok
        assert not approval.verify_token(t, PID, DDL.replace("region", "country")).ok
        assert not approval.verify_token(t, PID, DDL, now=time.time() + 10_000).ok
        assert approval.verify_token(t, PID, DDL).ok


class TestSecretConfig:
    @pytest.mark.parametrize("secret", ["", "short", "CHANGE_ME_TO_RANDOM_64_CHAR_HEX_STRING"])
    def test_issue_refuses_bad_secret(self, security_env, monkeypatch, secret):
        monkeypatch.setenv("APPROVAL_SECRET", secret)
        with pytest.raises(approval.ApprovalConfigError):
            approval.issue_token(PID, DDL)
        assert approval.is_configured() is False

    def test_verify_fails_closed_without_secret(self, security_env, monkeypatch):
        t = approval.issue_token(PID, DDL).token
        monkeypatch.setenv("APPROVAL_SECRET", "")
        assert approval.verify_token(t, PID, DDL).reason == "NO_SECRET"

    def test_issue_requires_inputs(self, security_env):
        with pytest.raises(ValueError):
            approval.issue_token("", DDL)
        with pytest.raises(ValueError):
            approval.issue_token(PID, "")


class TestAuditLogAppendOnly:
    def test_cannot_update_or_delete(self, security_env):
        from mcp_server.store import audit_log
        from mcp_server.store.meta_db import get_meta_conn
        aid = audit_log.log("apply_optimization", "rejected", proposal_id=PID, error_code="TOKEN_INVALID")
        assert aid.startswith("a_")
        with get_meta_conn() as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute("UPDATE audit_log SET result='success'")
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM audit_log")
        assert audit_log.count_by(error_code="TOKEN_INVALID") == 1
