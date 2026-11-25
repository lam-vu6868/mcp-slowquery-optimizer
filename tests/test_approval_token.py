"""
tests/test_approval_token.py
----------------------------

CHỨC NĂNG :
    Test approval token: sai chữ ký, hết hạn, dùng lại, khác DDL, thiếu token.

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ

THAM KHẢO  : security/approval.py

TRẠNG THÁI : ĐANG LÀM — kiểm tra token độc lập trước khi nối Tool 6.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest

from security.approval import ApprovalTokens

DDL = "ALTER TABLE `orders` ALTER INDEX `idx_orders_status_date` VISIBLE"


def test_token_is_single_use_and_survives_reopen(tmp_path):
    path = tmp_path / "tokens.sqlite3"
    tokens = ApprovalTokens(path, secret="test-only-secret", clock=lambda: 1000)
    token = tokens.issue_token("p_abc", 1, DDL)

    reopened = ApprovalTokens(path, secret="test-only-secret", clock=lambda: 1001)
    assert reopened.verify_token(token, "p_abc", 1, DDL)
    assert not tokens.verify_token(token, "p_abc", 1, DDL)


@pytest.mark.parametrize("proposal_id,version,ddl", [
    ("p_other", 1, DDL),
    ("p_abc", 2, DDL),
    ("p_abc", 1, DDL + " "),
])
def test_token_is_bound_to_exact_action(tmp_path, proposal_id, version, ddl):
    tokens = ApprovalTokens(tmp_path / "tokens.sqlite3", secret="test-only-secret",
                            clock=lambda: 1000)
    token = tokens.issue_token("p_abc", 1, DDL)
    assert not tokens.verify_token(token, proposal_id, version, ddl)
    assert tokens.verify_token(token, "p_abc", 1, DDL)


def test_invalid_signature_missing_and_expired_token(tmp_path):
    path = tmp_path / "tokens.sqlite3"
    issuer = ApprovalTokens(path, secret="test-only-secret", clock=lambda: 1000)
    token = issuer.issue_token("p_abc", 1, DDL)
    assert not issuer.verify_token("", "p_abc", 1, DDL)
    assert not issuer.verify_token(token + "x", "p_abc", 1, DDL)
    late = ApprovalTokens(path, secret="test-only-secret", clock=lambda: 1600)
    assert not late.verify_token(token, "p_abc", 1, DDL)


def test_missing_secret_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        ApprovalTokens(tmp_path / "tokens.sqlite3", secret="")


def test_different_secret_cannot_verify_token(tmp_path):
    path = tmp_path / "tokens.sqlite3"
    token = ApprovalTokens(path, secret="first-secret").issue_token("p_abc", 1, DDL)
    assert not ApprovalTokens(path, secret="second-secret").verify_token(
        token, "p_abc", 1, DDL,
    )


def test_simultaneous_use_has_one_winner(tmp_path):
    path = tmp_path / "tokens.sqlite3"
    tokens = ApprovalTokens(path, secret="test-only-secret")
    token = tokens.issue_token("p_abc", 1, DDL)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: ApprovalTokens(path, secret="test-only-secret").verify_token(
                token, "p_abc", 1, DDL,
            ), range(2),
        ))
    assert sorted(results) == [False, True]
