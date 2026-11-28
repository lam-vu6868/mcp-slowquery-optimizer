"""AppTest cho Dashboard Tab 4 — Bảo mật (dashboard/pages/4_security.py)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_tab4_security_renders_20_cases():
    page = Path(__file__).resolve().parents[1] / "dashboard" / "pages" / "4_security.py"
    at = AppTest.from_file(page)
    at.run(timeout=15)
    assert not at.exception
    assert any("Bảo mật" in t.value for t in at.title)
    # Kiểm tra bảng 20 kịch bản đã được nạp (metric hiển thị 20/20)
    metric_values = [str(m.value) for m in at.metric]
    assert "20" in metric_values
    assert "20/20" in metric_values
