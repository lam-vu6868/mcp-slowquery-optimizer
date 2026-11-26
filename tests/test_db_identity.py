"""Kiểm tra danh tính DB được đọc từ kết nối readonly đang dùng."""

from contextlib import contextmanager

import pytest

from mcp_server.utils import db


def test_current_db_identity_reads_server_and_schema(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            assert "@@server_uuid" in sql

        def fetchone(self):
            return {"server_uuid": "db-a", "schema_name": "shopdb"}

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def readonly():
        yield Connection()

    monkeypatch.setattr(db, "get_conn", readonly)
    identity = db.current_db_identity()
    assert identity == {"server_uuid": "db-a", "schema": "shopdb",
                        "host": db.Config.DB_HOST, "port": db.Config.DB_PORT}


def test_current_db_identity_refuses_missing_server_uuid(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            pass

        def fetchone(self):
            return {"server_uuid": None, "schema_name": "shopdb"}

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def readonly():
        yield Connection()

    monkeypatch.setattr(db, "get_conn", readonly)
    with pytest.raises(ValueError, match="danh tính DB"):
        db.current_db_identity()
