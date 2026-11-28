"""Unit tests cho metrics comparison.csv và Dashboard Tab 3 (3_comparison.py)."""

import csv
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from data.metrics.metrics import (
    build_comparison_rows,
    summarize_rewrite_reports,
    write_comparison_csv,
)


def test_summarize_rewrite_reports_and_write_csv(tmp_path):
    (tmp_path / "q14_rewrite_measure.json").write_text(
        json.dumps({
            "query_id": "q14",
            "status": "passed",
            "failure_reason": None,
            "before": {"p95_ms": 1000.0, "query_cost": 500.0, "rows_examined": 10000},
            "after": {"p95_ms": 200.0, "query_cost": 100.0, "rows_examined": 1000},
        }),
        encoding="utf-8",
    )
    (tmp_path / "q30_rewrite_measure.json").write_text(
        json.dumps({
            "query_id": "q30",
            "status": "failed",
            "failure_reason": "result_changed",
            "before": {"p95_ms": 2000.0, "query_cost": 600.0, "rows_examined": 20000},
            "after": {"p95_ms": 1800.0, "query_cost": 700.0, "rows_examined": 21000},
        }),
        encoding="utf-8",
    )

    summary = summarize_rewrite_reports(tmp_path)
    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["pass_rate"] == 0.5
    assert summary["items"][0]["p95_improvement_pct"] == 80.0

    rows = build_comparison_rows(rewrite_dir=tmp_path)
    assert len(rows) == 2
    assert [r["method"] for r in rows] == ["llm_groq_mcp", "greedy"]

    csv_path = write_comparison_csv(tmp_path / "comparison.csv", rows)
    assert csv_path.is_file()
    with csv_path.open(encoding="utf-8", newline="") as fh:
        loaded = list(csv.DictReader(fh))
    assert len(loaded) == 2
    assert loaded[0]["method"] == "llm_groq_mcp"
    assert loaded[0]["rewrite_passed"] == "1"


def test_dashboard_tab4_comparison_renders_without_error():
    page = Path(__file__).resolve().parents[1] / "dashboard" / "pages" / "4_so_sanh.py"
    at = AppTest.from_file(page)
    at.run(timeout=15)
    assert not at.exception
    assert any("So sánh" in t.value for t in at.title)
