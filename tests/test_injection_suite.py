"""
tests/test_injection_suite.py
-----------------------------
CHỨC NĂNG: Chạy 20 kịch bản injection trong CI — kịch bản nào lọt là test đỏ.
PHỤ TRÁCH: Tình    |    REVIEW: Vũ
THAM KHẢO: security/injection_tests/
"""
import pytest

from security.injection_tests import run_tests
from security.injection_tests.payloads import PAYLOADS


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    tmp = tmp_path_factory.mktemp("inj")
    mp.setattr(run_tests, "LOG_DIR", tmp)
    mp.setenv("META_DB_PATH", str(tmp / "meta.sqlite3"))
    mp.setenv("APPROVAL_SECRET", "ci_secret_" + "c" * 50)
    try:
        yield run_tests.run(use_db=False)
    finally:
        mp.undo()


def test_twenty_scenarios_four_groups():
    assert len(PAYLOADS) == 20
    assert {p["group"] for p in PAYLOADS} == set("ABCD")


@pytest.mark.parametrize("pid", [p["id"] for p in PAYLOADS])
def test_scenario_blocked(report, pid):
    r = next(x for x in report["results"] if x["id"] == pid)
    leaked = [l for l in r["layers"] if l["status"] == "NOT_BLOCKED"]
    assert r["blocked"], f"{pid} lọt qua: {leaked}"


def test_tool6_scenarios_are_audited(report):
    for r in report["results"]:
        if r["audit_logged"] is not None:
            assert r["audit_logged"] is True, r["id"]
