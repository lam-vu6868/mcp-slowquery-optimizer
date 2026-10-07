import pytest

from security.approval import issue_token, verify_token, reset_used_tokens


@pytest.fixture(autouse=True)
def reset_tokens():
    reset_used_tokens()
    yield
    reset_used_tokens()


def test_issue_and_verify_valid_token():
    ddl = "CREATE INDEX idx_orders_status_created ON orders (status, created_at)"
    token = issue_token("proposal-1", ddl, secret="test-secret")

    assert verify_token(token, "proposal-1", ddl, secret="test-secret") is True


def test_rejects_wrong_secret_or_ddl():
    ddl = "CREATE INDEX idx_orders_status_created ON orders (status, created_at)"
    token = issue_token("proposal-1", ddl, secret="test-secret")

    assert verify_token(token, "proposal-1", "CREATE INDEX idx_other ON orders (status)", secret="test-secret") is False
    assert verify_token(token, "proposal-1", ddl, secret="wrong-secret") is False


def test_rejects_expired_token():
    ddl = "CREATE INDEX idx_orders_status_created ON orders (status, created_at)"
    token = issue_token("proposal-1", ddl, secret="test-secret", expires_in=-1)

    assert verify_token(token, "proposal-1", ddl, secret="test-secret") is False


def test_rejects_reused_token():
    ddl = "CREATE INDEX idx_orders_status_created ON orders (status, created_at)"
    token = issue_token("proposal-1", ddl, secret="test-secret")

    assert verify_token(token, "proposal-1", ddl, secret="test-secret") is True
    assert verify_token(token, "proposal-1", ddl, secret="test-secret") is False
