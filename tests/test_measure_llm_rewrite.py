"""Kiểm phép đo offline rewrite + tập index LLM bằng tool và trial giả.
PHỤ TRÁCH: Vũ | REVIEW: Hải.
THAM KHẢO: docs/api-contract.md mục 2.2, ROADMAP mục 2.4.
"""

import json

import pytest

from mcp_server.store.proposals import ProposalStore
from scripts.measure_llm_rewrite import (
    load_saved_rewrite,
    measure_rewrite_with_indexes,
    preflight_validation_lab,
)

SQL = "SELECT id FROM orders"
REWRITE = "SELECT id FROM orders WHERE id > 0"
INDEXES = [
    {"table": "orders", "index_name": "idx_orders_a"},
    {"table": "orders", "index_name": "idx_orders_b"},
]


def test_loads_exact_saved_rewrite_and_indexes_without_creating_store(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(FileNotFoundError):
        load_saved_rewrite(missing, "q14", SQL)
    assert not missing.exists()

    path = tmp_path / "q14.sqlite3"
    store = ProposalStore(path)
    store.add_many("q14", SQL, [
        {"type": "index", "table": "orders", "index_name": "idx_orders_a",
         "columns": [{"name": "id", "order": "ASC"}]},
        {"type": "rewrite", "original_query_id": "q14",
         "rewritten_sql": REWRITE},
    ])
    loaded = load_saved_rewrite(path, "q14", SQL)
    assert loaded["rewritten_sql"] == REWRITE
    assert [index["index_name"] for index in loaded["indexes"]] == ["idx_orders_a"]
    with pytest.raises(ValueError, match="catalog"):
        load_saved_rewrite(path, "q14", "SELECT id FROM addresses")


def test_preflight_checks_lab_marker_and_all_index_snapshots(monkeypatch):
    from scripts import measure_llm_rewrite as module

    monkeypatch.setattr(module.Config, "DB_HOST", "127.0.0.1")
    monkeypatch.setattr(module.Config, "DB_PORT", 3307)
    monkeypatch.setattr(module.Config, "DB_NAME", "shopdb")
    monkeypatch.setattr(module.Config, "DB_USER", "readonly_user")
    monkeypatch.setattr(module.Config, "DB_ADMIN_USER", "index_admin")
    events = []

    class Trial:
        def __init__(self, proposal):
            self.name = proposal["index_name"]

        def fk_support_snapshot(self):
            events.append(("snapshot", self.name))
            return {"foreign_keys": [], "supporting_indexes": []}

        def _check_schema(self, fk_snapshot=None):
            events.append(("schema", self.name))

    with pytest.raises(ValueError, match="3309"):
        preflight_validation_lab(INDEXES, trial_factory=Trial,
                                 marker_reader=lambda: "mcp-validation-lab-v1")
    assert events == []

    monkeypatch.setattr(module.Config, "DB_PORT", 3309)
    with pytest.raises(ValueError, match="marker"):
        preflight_validation_lab(INDEXES, trial_factory=Trial,
                                 marker_reader=lambda: "wrong")
    assert events == []

    snapshots = preflight_validation_lab(
        INDEXES, trial_factory=Trial,
        marker_reader=lambda: "mcp-validation-lab-v1",
    )
    assert set(snapshots) == {"idx_orders_a", "idx_orders_b"}
    assert events == [("snapshot", "idx_orders_a"), ("schema", "idx_orders_a"),
                      ("snapshot", "idx_orders_b"), ("schema", "idx_orders_b")]


@pytest.mark.asyncio
async def test_measures_original_vs_rewrite_with_full_index_set_and_cleans_up():
    events = []

    class Trial:
        def __init__(self, proposal):
            self.name = proposal["index_name"]

        def create(self, fk_snapshot=None):
            events.append(("create", self.name))

        def drop(self):
            events.append(("drop", self.name))

    async def explain(sql, *, mode, use_invisible_indexes):
        assert mode == "estimate"
        assert (sql, use_invisible_indexes) in ((SQL, False), (REWRITE, True))
        return json.dumps({"ok": True, "data": {
            "query_cost": 10, "raw_plan": {"table": {
                "table_name": "orders", "key": "idx_orders_a",
            }},
        }})

    async def benchmark(sql, *, warmup_runs, measured_runs,
                        use_invisible_indexes, compute_result_hash):
        assert (warmup_runs, measured_runs, compute_result_hash) == (3, 20, True)
        return json.dumps({"ok": True, "data": {
            "p95_ms": 50 if use_invisible_indexes else 100,
            "rows_examined": 10, "result_hash": "same", "row_count": 2,
            "runs": 20, "timed_out_runs": 0,
        }})

    result = await measure_rewrite_with_indexes(
        query_id="q14", original_sql=SQL, rewritten_sql=REWRITE,
        indexes=INDEXES, trial_factory=Trial, explain=explain, benchmark=benchmark,
    )
    assert result["status"] == "passed"
    assert result["index_usage"] == {"idx_orders_a": True, "idx_orders_b": False}
    assert result["approvable"] is False
    assert events == [("create", "idx_orders_a"), ("create", "idx_orders_b"),
                      ("drop", "idx_orders_b"), ("drop", "idx_orders_a")]


@pytest.mark.asyncio
async def test_rejects_bad_rewrite_before_any_trial():
    events = []
    result = await measure_rewrite_with_indexes(
        query_id="q14", original_sql=SQL, rewritten_sql="DELETE FROM orders",
        indexes=INDEXES, trial_factory=lambda proposal: events.append(proposal),
    )
    assert result["status"] == "inconclusive"
    assert result["failure_reason"] == "ast_rejected"
    assert events == []


@pytest.mark.asyncio
async def test_partial_create_failure_still_drops_started_trials():
    events = []

    class Trial:
        def __init__(self, proposal):
            self.name = proposal["index_name"]

        def create(self, fk_snapshot=None):
            events.append(("create", self.name))
            if self.name == "idx_orders_b":
                raise RuntimeError("create failed")

        def drop(self):
            events.append(("drop", self.name))

    result = await measure_rewrite_with_indexes(
        query_id="q14", original_sql=SQL, rewritten_sql=REWRITE,
        indexes=INDEXES, trial_factory=Trial,
    )
    assert result["status"] == "inconclusive"
    assert result["failure_reason"] == "measurement_error"
    assert events == [("create", "idx_orders_a"), ("create", "idx_orders_b"),
                      ("drop", "idx_orders_b"), ("drop", "idx_orders_a")]


@pytest.mark.asyncio
@pytest.mark.parametrize(("after_hash", "after_runs", "expected", "reason"), [
    ("different", 20, "failed", "result_changed"),
    ("same", 19, "inconclusive", "measurement_incomplete"),
])
async def test_bad_result_or_short_measurement_never_passes(
    after_hash, after_runs, expected, reason,
):
    events = []

    class Trial:
        def __init__(self, proposal):
            self.name = proposal["index_name"]

        def create(self, fk_snapshot=None):
            events.append("create")

        def drop(self):
            events.append("drop")

    async def explain(sql, *, mode, use_invisible_indexes):
        return json.dumps({"ok": True, "data": {"query_cost": 10, "raw_plan": {}}})

    async def benchmark(sql, *, warmup_runs, measured_runs,
                        use_invisible_indexes, compute_result_hash):
        return json.dumps({"ok": True, "data": {
            "p95_ms": 50 if use_invisible_indexes else 100,
            "rows_examined": 10,
            "result_hash": after_hash if use_invisible_indexes else "same",
            "row_count": 2,
            "runs": after_runs if use_invisible_indexes else 20,
            "timed_out_runs": 0,
        }})

    result = await measure_rewrite_with_indexes(
        query_id="q14", original_sql=SQL, rewritten_sql=REWRITE,
        indexes=INDEXES, trial_factory=Trial, explain=explain, benchmark=benchmark,
    )
    assert (result["status"], result["failure_reason"]) == (expected, reason)
    assert events == ["create", "create", "drop", "drop"]


@pytest.mark.asyncio
async def test_cleanup_failure_overrides_measurement_result():
    class Trial:
        def __init__(self, proposal):
            pass

        def create(self, fk_snapshot=None):
            pass

        def drop(self):
            raise RuntimeError("cannot clean")

    result = await measure_rewrite_with_indexes(
        query_id="q14", original_sql=SQL, rewritten_sql=REWRITE,
        indexes=INDEXES, trial_factory=Trial,
        explain=lambda *args, **kwargs: None,
    )
    assert result["status"] == "inconclusive"
    assert result["failure_reason"] == "cleanup_failed"


# ---------------------------------------------------------------------------
# Test save/load snapshot và CLI --dry-run
# ---------------------------------------------------------------------------

from scripts.measure_llm_rewrite import (
    _build_parser,
    load_preflight_snapshot,
    main,
    save_preflight_snapshot,
)


def test_save_and_load_preflight_snapshot_roundtrip(tmp_path):
    """Lưu rồi đọc lại snapshot; query_id khác thì raise ValueError."""
    snap = {"idx_orders_a": {"foreign_keys": [], "supporting_indexes": []}}
    path = tmp_path / "q14.snapshot.json"

    save_preflight_snapshot(path, "q14", snap)
    assert path.is_file()

    loaded = load_preflight_snapshot(path, "q14")
    assert loaded == snap

    # query_id không khớp
    with pytest.raises(ValueError, match="query_id"):
        load_preflight_snapshot(path, "q99")


def test_save_snapshot_overwrites_existing(tmp_path):
    """File cũ bị ghi đè để snapshot luôn phản ánh trạng thái mới nhất."""
    path = tmp_path / "sub" / "snap.json"
    save_preflight_snapshot(path, "q14", {"idx_a": {"v": 1}})
    save_preflight_snapshot(path, "q14", {"idx_a": {"v": 2}})
    loaded = load_preflight_snapshot(path, "q14")
    assert loaded["idx_a"]["v"] == 2


def test_load_snapshot_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_preflight_snapshot(tmp_path / "missing.json", "q14")


def test_cli_dry_run_prints_status_and_saves_snapshot(tmp_path, monkeypatch):
    """CLI --dry-run: load + preflight + snapshot; không tạo DDL."""
    import scripts.measure_llm_rewrite as module

    # Dùng SQL giả khớp catalog giả để tránh phụ thuộc QUERIES thật
    FAKE_SQL = "SELECT id FROM orders WHERE id > 0"
    FAKE_REWRITE = "SELECT id FROM orders WHERE id > 1"

    store_path = tmp_path / "q99.sqlite3"
    snap_path = tmp_path / "q99.snapshot.json"

    # Chuẩn bị store có đúng 1 rewrite + 1 index với SQL giả
    store = ProposalStore(store_path)
    store.add_many("q99", FAKE_SQL, [
        {"type": "index", "table": "orders", "index_name": "idx_orders_a",
         "columns": [{"name": "id", "order": "ASC"}]},
        {"type": "rewrite", "original_query_id": "q99", "rewritten_sql": FAKE_REWRITE},
    ])

    # Patch catalog để main() thấy q99 với SQL giả
    import data.queries.queries as qmod
    monkeypatch.setattr(qmod, "QUERIES", [{"id": "q99", "sql": FAKE_SQL}])

    # Giả lập preflight trả snapshot giả, không kết nối DB
    captured_snapshots = {}

    def fake_preflight(indexes, **_kwargs):
        for idx in indexes:
            captured_snapshots[idx["index_name"]] = {"foreign_keys": [], "supporting_indexes": []}
        return captured_snapshots

    monkeypatch.setattr(module, "preflight_validation_lab", fake_preflight)

    outputs = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: outputs.append(" ".join(str(x) for x in a)))

    import sys
    monkeypatch.setattr(sys, "argv", [
        "measure_llm_rewrite",
        "q99", str(store_path),
        "--dry-run",
        "--snapshot", str(snap_path),
    ])
    main()

    assert snap_path.is_file()
    snap = load_preflight_snapshot(snap_path, "q99")
    assert "idx_orders_a" in snap
    combined = " ".join(outputs)
    assert "dry_run" in combined


def test_cli_parser_defaults():
    """Parser có đúng các argument bắt buộc và tùy chọn."""
    parser = _build_parser()
    args = parser.parse_args(["q14", "some/path.sqlite3", "--dry-run"])
    assert args.query_id == "q14"
    assert args.store_path == "some/path.sqlite3"
    assert args.dry_run is True
    assert args.output is None

    args2 = parser.parse_args(["q14", "some/path.sqlite3", "--output", "out.json",
                               "--timeout-ms", "60000"])
    assert args2.dry_run is False
    assert args2.output == "out.json"
    assert args2.timeout_ms == 60000


@pytest.mark.asyncio
async def test_timeout_ms_passed_and_validated():
    """timeout_ms hợp lệ được truyền tới benchmark; ngoài [1000, 60000] bị từ chối."""
    events = []
    seen_timeouts = []

    class Trial:
        def __init__(self, proposal):
            self.name = proposal["index_name"]

        def create(self, fk_snapshot=None):
            events.append("create")

        def drop(self):
            events.append("drop")

    bad = await measure_rewrite_with_indexes(
        query_id="q16", original_sql=SQL, rewritten_sql=REWRITE,
        indexes=INDEXES, trial_factory=Trial, timeout_ms=70000,
    )
    assert bad["failure_reason"] == "proposal_context_invalid"
    assert events == []

    async def explain(sql, *, mode, use_invisible_indexes):
        return json.dumps({"ok": True, "data": {"query_cost": 10, "raw_plan": {}}})

    async def benchmark(sql, *, warmup_runs, measured_runs,
                        use_invisible_indexes, compute_result_hash, timeout_ms=None):
        seen_timeouts.append(timeout_ms)
        return json.dumps({"ok": True, "data": {
            "p95_ms": 50 if use_invisible_indexes else 100,
            "rows_examined": 10, "result_hash": "same", "row_count": 2,
            "runs": 20, "timed_out_runs": 0,
        }})

    ok = await measure_rewrite_with_indexes(
        query_id="q16", original_sql=SQL, rewritten_sql=REWRITE,
        indexes=INDEXES, trial_factory=Trial, explain=explain,
        benchmark=benchmark, timeout_ms=60000,
    )
    assert ok["status"] == "passed"
    assert seen_timeouts == [60000, 60000]
