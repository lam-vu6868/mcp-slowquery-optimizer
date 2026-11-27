"""Bộ 20 kịch bản chạy trên ranh giới code, không gọi Groq hoặc MySQL."""

from collections import Counter

from security.injection_tests.payloads import PAYLOADS
from security.injection_tests.run_tests import run_cases


def test_injection_suite_covers_four_channels_and_records_results(tmp_path):
    assert len(PAYLOADS) == len({item["id"] for item in PAYLOADS}) == 20
    assert Counter(item["group"] for item in PAYLOADS) == {
        "A": 5, "B": 5, "C": 5, "D": 5,
    }

    log_path = tmp_path / "injection_results.log"
    results = run_cases(log_path)

    assert len(results) == 20
    assert all(item["status"] == "blocked" for item in results)
    assert next(item for item in results if item["id"] == "D05")["audit_log"] is True
    assert all(item["llm_influenced"] == "not_measured" for item in results)
    assert log_path.is_file()
