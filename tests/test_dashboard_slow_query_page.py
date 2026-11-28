"""Kiểm trang Slow Query và đường chuyển dữ liệu sang form Đề xuất bằng Tool 1 giả."""

import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dashboard import backend


@pytest.mark.asyncio
async def test_load_slow_queries_accepts_only_marked_tool1_rows(monkeypatch):
    async def fake_tool(**kwargs):
        assert kwargs == {"limit": 10, "source": "performance_schema"}
        return json.dumps({"ok": True, "data": {"queries": [{
            "query_id": "digest-1", "sql_text": "SELECT 1", "untrusted": True,
            "avg_latency_ms": 610, "exec_count": 2,
        }]}})

    monkeypatch.setattr(backend, "get_slow_queries", fake_tool, raising=False)
    rows = await backend.load_slow_queries("performance_schema")
    assert rows[0]["query_id"] == "digest-1"

    async def unmarked(**_):
        return json.dumps({"ok": True, "data": {"queries": [{
            "query_id": "digest-1", "sql_text": "SELECT 1", "untrusted": False,
        }]}})

    monkeypatch.setattr(backend, "get_slow_queries", unmarked)
    with pytest.raises(ValueError, match="Tool 1"):
        await backend.load_slow_queries("performance_schema")


def test_slow_query_page_hands_selected_sql_to_proposal_form(monkeypatch):
    rows = [{"query_id": "slowlog:abc", "sql_text": "SELECT 1", "untrusted": True,
             "avg_latency_ms": 720, "exec_count": 1, "rows_examined_avg": 4}]

    async def fake_load(source):
        assert source == "performance_schema"
        return rows

    destinations = []
    monkeypatch.setattr(backend, "load_slow_queries", fake_load, raising=False)
    monkeypatch.setattr(st, "switch_page", lambda path: destinations.append(path))
    page = Path(backend.__file__).parent / "pages" / "1_chon_query_cham.py"
    at = AppTest.from_file(str(page))
    at.run()
    assert not at.exception
    next(button for button in at.button if button.label == "Tải slow query").click().run()
    assert not at.exception
    next(button for button in at.button if button.label == "Phân tích query này").click().run()
    assert at.session_state["analysis_query_id"] == "slowlog:abc"
    assert at.session_state["analysis_sql"] == "SELECT 1"
    assert destinations == ["pages/2_llm_de_xuat.py"]


def test_proposal_form_prefills_selected_slow_query():
    store = type("Store", (), {"recent_proposals": lambda self: []})()
    page = Path(backend.__file__).parent / "pages" / "2_llm_de_xuat.py"
    at = AppTest.from_file(str(page))
    at.session_state["proposal_store"] = store
    at.session_state["analysis_query_id"] = "digest-1"
    at.session_state["analysis_sql"] = "SELECT 1"
    at.run()
    assert not at.exception
    assert at.text_input[0].value == "digest-1"
    assert at.text_area[0].value == "SELECT 1"
