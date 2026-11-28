"""AppTest cho Trang 5 — Bảo mật (dashboard/pages/5_bao_mat.py)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_tab5_security_runs_20_cases_live():
    page = Path(__file__).resolve().parents[1] / "dashboard" / "pages" / "5_bao_mat.py"
    at = AppTest.from_file(page)
    at.run(timeout=15)
    assert not at.exception
    assert any("Bảo mật" in t.value for t in at.title)
    # Chưa bấm chạy -> chưa hiện bảng kết quả live
    assert any("Chưa chạy bộ kiểm thử" in i.value for i in at.info)

    run_btn = next(b for b in at.button if "Chạy 20 kịch bản" in b.label)
    run_btn.click().run(timeout=30)
    assert not at.exception
    metric_values = [str(m.value) for m in at.metric]
    assert "20" in metric_values
    assert "20/20" in metric_values
