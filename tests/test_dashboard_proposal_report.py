"""Trang Đề xuất cho người duyệt thấy số đo đã lưu trước khi quyết định."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from dashboard import backend


def test_proposals_page_shows_validation_tradeoff():
    report = {
        "status": "passed", "evidence_complete": True,
        "result_equivalent": True,
        "before": {"p95_ms": 2261.62},
        "after": {"p95_ms": 1137.69},
        "write_overhead": {
            "insert_throughput_change_pct": -21.73,
            "index_size_bytes": 73072640,
            "sample_rows": 100000,
        },
    }
    saved = {
        "proposal_id": "p_test", "query_id": "q07",
        "original_sql": "SELECT 1", "trial_state": "cleaned",
        "proposal": {"type": "index", "table": "orders", "index_name": "idx_test"},
        "report": report,
    }
    store = type("Store", (), {"recent_proposals": lambda self: [saved]})()
    page = Path(backend.__file__).parent / "pages" / "2_proposals.py"
    at = AppTest.from_file(str(page))
    at.session_state["proposal_store"] = store
    at.run()

    assert not at.exception
    metrics = {item.label: item.value for item in at.metric}
    assert metrics["P95 trước"] == "2261.62 ms"
    assert metrics["P95 sau"] == "1137.69 ms"
    assert metrics["Thay đổi thông lượng INSERT"] == "-21.73%"
    assert metrics["Dung lượng index thử (ước tính)"] == "69.69 MiB"
    assert any("100,000 dòng" in item.value for item in at.caption)
    assert any("Kết quả tương đương: có" in item.value for item in at.text)
