"""
tests/test_dashboard_smoke.py
-----------------------------

CHỨC NĂNG :
    Smoke test Dashboard: trang chủ + 4 tab phải chạy KHÔNG lỗi khi chưa có
    dữ liệu (tuần 1 từng crash khi bảng trống) và khi MySQL chưa chạy.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

CHẠY      : pytest tests/test_dashboard_smoke.py -v
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard"
PAGES = ["app.py"] + sorted(p.relative_to(DASHBOARD).as_posix() for p in (DASHBOARD / "pages").glob("*.py"))


@pytest.mark.parametrize("page", PAGES)
def test_page_runs_without_data(page, monkeypatch):
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", "1")  # cổng chắc chắn không có MySQL
    at = AppTest.from_file(str(DASHBOARD / page), default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]


def test_has_four_tabs():
    assert len(PAGES) == 5
