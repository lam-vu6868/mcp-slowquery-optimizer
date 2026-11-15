"""
tests/conftest.py
-----------------
Fixture dùng chung. KHÔNG autouse để không ảnh hưởng test của người khác.

security_env: trỏ SQLite meta sang thư mục tạm + đặt APPROVAL_SECRET giả cho test.
"""
import pytest

TEST_SECRET = "test_secret_" + "a" * 52  # >= 32 ký tự, không phải giá trị mẫu


@pytest.fixture
def security_env(tmp_path, monkeypatch):
    monkeypatch.setenv("META_DB_PATH", str(tmp_path / "meta.sqlite3"))
    monkeypatch.setenv("APPROVAL_SECRET", TEST_SECRET)
    monkeypatch.setenv("APPROVAL_TOKEN_TTL", "600")
    return tmp_path
