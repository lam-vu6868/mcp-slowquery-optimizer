"""
scripts/lab_demo_runner.py
--------------------------

CHỨC NĂNG : Tiến trình riêng cho Dashboard: đo trước/sau trên validation lab 3309 cho
            (1) đề xuất LLM đã lưu hoặc (2) đề xuất của baseline Greedy.
PHỤ TRÁCH  : Vũ · Tình    |    REVIEW: Hải

LƯU Ý:
    - Chỉ chạy khi DB_PORT=3309 (Dashboard tự đặt biến môi trường); preflight kiểm marker
      `mcp-validation-lab-v1` và snapshot FK/index trước khi tạo bất kỳ index thử nào.
    - Chế độ quick = 1 warm-up + 3 lượt (nhãn "chưa phải kết quả chính thức");
      chế độ full = đúng ngưỡng trong config/settings.yaml (3 warm-up + 20 lượt).
    - Luôn ghi result.json cuối cùng (kể cả lỗi) để Dashboard biết tiến trình đã kết thúc.
    - Kết quả luôn `approvable=false`: phép đo demo không cấp token Tool 6.

Chạy tay:
    python -m scripts.lab_demo_runner measure --request req.json --out result.json
"""

import argparse
import asyncio
import hashlib
import json
import os
import time
import traceback
from pathlib import Path

from mcp_server.store.proposals import ProposalStore
from security.ast_whitelist import check as ast_check

ROOT = Path(__file__).resolve().parents[1]
QUICK_RUNS = (1, 5)  # (warm-up, lượt đo) — benchmark_query yêu cầu tối thiểu 5 lượt
MAX_INDEXES = 3
FAST_HASH_SORT_LIMIT = 10000


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def select_proposals(items: list[dict]) -> dict:
    """Từ các đề xuất đã lưu lấy 1 rewrite và tối đa 3 index không trùng tên."""
    rewrite = None
    indexes: list[dict] = []
    seen: set[str] = set()
    for item in items:
        proposal = item["proposal"]
        if proposal.get("type") == "rewrite":
            if rewrite is None:
                rewrite = proposal["rewritten_sql"]
        elif (proposal.get("type") == "index"
              and proposal["index_name"] not in seen
              and len(indexes) < MAX_INDEXES):
            seen.add(proposal["index_name"])
            indexes.append(proposal)
    return {"rewritten_sql": rewrite, "indexes": indexes}


def load_request_proposals(store_path: Path, request: dict) -> list[dict]:
    """Đọc đúng các đề xuất của lượt phân tích hiện tại (hoặc mới nhất của query)."""
    store = ProposalStore(store_path)
    ids = request.get("proposal_ids") or []
    if ids:
        items = [store.get(proposal_id) for proposal_id in ids]
    else:
        items = [item for item in store.recent_proposals()
                 if item["query_id"] == request["query_id"]]
    for item in items:
        if item["query_id"] != request["query_id"] or item["original_sql"] != request["sql"]:
            raise ValueError("đề xuất không khớp query đang làm việc")
    return items


def _default_preflight(indexes: list[dict]) -> dict:
    from scripts.measure_llm_rewrite import preflight_validation_lab
    if indexes:
        return preflight_validation_lab(indexes)
    # Chỉ rewrite: vẫn phải xác nhận đúng lab trước khi đo.
    preflight_validation_lab([{"type": "index", "table": "orders", "index_name": "idx_probe",
                               "columns": [{"name": "status", "order": "ASC"}]}],
                             trial_factory=_NoCheckTrial)
    return {}


class _NoCheckTrial:
    """Giả lập cho nhánh rewrite-only: chỉ để preflight đọc marker, không đọc schema."""

    def __init__(self, _proposal):
        pass

    def fk_support_snapshot(self):
        return {}

    def _check_schema(self, fk_snapshot=None):
        return None


def _default_greedy(sql: str, query_id: str) -> dict:
    from data.baseline.greedy import greedy_select_indexes, make_lab_cost_evaluator
    return greedy_select_indexes(
        sql, cost_evaluator=make_lab_cost_evaluator(), query_id=query_id,
        max_columns=2, max_indexes=1,
    )


def _run_fast_once(sql: str, *, use_invisible_indexes: bool, timeout_ms: int = 60000) -> dict:
    """Chạy đúng 1 lượt SELECT trên lab, trả latency_ms, rows_examined, row_count, result_hash."""
    import pymysql.cursors

    from dashboard.query_runner import _handler_reads
    from mcp_server.utils.db import get_conn

    switch = "use_invisible_indexes=on" if use_invisible_indexes else "use_invisible_indexes=off"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {int(timeout_ms)}")
            cur.execute(f"SET SESSION optimizer_switch = '{switch}'")
        reads_before = _handler_reads(conn)
        t0 = time.perf_counter()
        row_count = 0
        encoded_rows: list[str] = []
        hasher = hashlib.sha256()
        overflow = False
        with conn.cursor(pymysql.cursors.SSCursor) as stream_cur:
            stream_cur.execute(sql)
            while True:
                batch = stream_cur.fetchmany(1000)
                if not batch:
                    break
                for row in batch:
                    line = json.dumps([str(v) if v is not None else None for v in row],
                                      ensure_ascii=False)
                    if not overflow:
                        encoded_rows.append(line)
                        if len(encoded_rows) > FAST_HASH_SORT_LIMIT:
                            overflow = True
                            for item in encoded_rows:
                                hasher.update((item + "\n").encode("utf-8"))
                            encoded_rows.clear()
                    else:
                        hasher.update((line + "\n").encode("utf-8"))
                row_count += len(batch)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        reads_after = _handler_reads(conn)
    if not overflow:
        encoded_rows.sort()
        for item in encoded_rows:
            hasher.update((item + "\n").encode("utf-8"))
    return {
        "p95_ms": elapsed_ms,
        "p50_ms": elapsed_ms,
        "rows_examined": max(0, reads_after - reads_before),
        "row_count": row_count,
        "result_hash": f"sha256:{hasher.hexdigest()}",
        "timed_out_runs": 0,
    }


def _default_fast_measure(*, query_id: str, original_sql: str, rewritten_sql: str,
                          indexes: list[dict], fk_snapshots: dict | None = None,
                          timeout_ms: int = 60000, progress=None,
                          trial_factory=None, explain=None, run_once=None, **_extra) -> dict:
    """Chế độ thử siêu nhanh: 1 lượt trước + 1 lượt sau, vẫn tạo/xóa index INVISIBLE an toàn."""
    from mcp_server.tools.apply import TrialIndex
    from mcp_server.tools.explain import explain_query
    from scripts.measure_llm_rewrite import _plan_uses_index, _settings, _tool_data

    factory = trial_factory or TrialIndex
    explain_fn = explain or explain_query
    once_fn = run_once or _run_fast_once
    report_progress = progress or (lambda _stage: None)
    settings = _settings()
    report = {
        "query_id": query_id, "status": "inconclusive", "failure_reason": None,
        "before": None, "after": None, "index_usage": {},
        "mode": "fast", "measured_runs": 1,
    }
    started = []
    try:
        for idx, proposal in enumerate(indexes, start=1):
            report_progress(
                f"Đang tạo index INVISIBLE tạm ({idx}/{len(indexes)}): "
                f"{proposal['table']}.{proposal['index_name']}"
            )
            trial = factory(proposal)
            started.append(trial)
            trial.create(fk_snapshot=(fk_snapshots or {}).get(proposal["index_name"]))

        for label, sql, enabled in (("before", original_sql, False),
                                    ("after", rewritten_sql, True)):
            side = "SQL gốc (trước tối ưu)" if not enabled else "đề xuất (sau tối ưu)"
            report_progress(f"Đang chạy thử 1 lượt {side}...")
            plan = _tool_data(asyncio.run(explain_fn(
                sql, mode="estimate", use_invisible_indexes=enabled,
            )))
            measured = once_fn(sql, use_invisible_indexes=enabled, timeout_ms=timeout_ms)
            report[label] = {**measured, "query_cost": float(plan["query_cost"])}
            if enabled:
                report["index_usage"] = {
                    item["index_name"]: _plan_uses_index(
                        plan.get("raw_plan"), rewritten_sql,
                        item["table"], item["index_name"],
                    ) for item in indexes
                }

        before, after = report["before"], report["after"]
        if (before["result_hash"] != after["result_hash"]
                or before["row_count"] != after["row_count"]):
            report.update(status="failed", failure_reason="result_changed")
        elif before["p95_ms"] <= 0:
            report.update(status="inconclusive", failure_reason="measurement_incomplete")
        elif ((before["p95_ms"] - after["p95_ms"]) / before["p95_ms"]
              < settings["min_p95_improvement_pct"] / 100):
            report.update(status="failed", failure_reason="p95_below_threshold")
        else:
            report["status"] = "passed"
    except Exception as exc:  # noqa: BLE001 - luôn cleanup kể cả khi lỗi
        report["failure_reason"] = "measurement_error"
        report["error_type"] = type(exc).__name__
    finally:
        if started:
            report_progress("Đang xóa index tạm trên lab 3309...")
        for trial in reversed(started):
            try:
                trial.drop()
            except Exception:  # noqa: BLE001
                report.update(status="inconclusive", failure_reason="cleanup_failed")
    return report


def _default_measure(**kwargs) -> dict:
    from mcp_server.tools.apply import TrialIndex
    from scripts.measure_llm_rewrite import measure_rewrite_with_indexes
    return asyncio.run(measure_rewrite_with_indexes(trial_factory=TrialIndex, **kwargs))


def run_measure(request: dict, *, store_path: Path, progress=lambda stage: None,
                preflight=None, greedy_runner=None, measure=None) -> dict:
    """Đo trước/sau cho đề xuất của `source`; trả báo cáo gọn để Dashboard hiển thị."""
    started = time.time()
    query_id, sql = request["query_id"], request["sql"]
    source, mode = request["source"], request["mode"]
    if source not in ("llm", "greedy") or mode not in ("fast", "quick", "full"):
        raise ValueError("source hoặc mode không hợp lệ")
    base = {"kind": "measure", "source": source, "query_id": query_id,
            "official": mode == "full", "approvable": False}
    if not ast_check(sql)[0]:
        return {**base, "status": "inconclusive", "failure_reason": "ast_rejected"}

    rewrite, indexes, greedy = None, [], None
    if source == "llm":
        progress("Đọc đề xuất LLM đã lưu")
        chosen = select_proposals(load_request_proposals(store_path, request))
        rewrite, indexes = chosen["rewritten_sql"], chosen["indexes"]
    else:
        progress("Greedy đang thử index ứng viên bằng EXPLAIN (khoảng 1–2 phút)")
        greedy = (greedy_runner or _default_greedy)(sql, query_id)
        indexes = greedy["proposals"]
    greedy_summary = ({"baseline_cost": greedy["baseline_cost"],
                       "final_cost": greedy["final_cost"],
                       "cost_reduction_pct": greedy["cost_reduction_pct"]}
                      if greedy else None)

    if rewrite is None and not indexes:
        return {**base, "status": "no_proposal", "failure_reason": "no_proposal",
                "greedy": greedy_summary, "elapsed_s": round(time.time() - started, 1)}

    progress("Kiểm tra marker và snapshot FK/index của lab 3309")
    snapshots = (preflight or _default_preflight)(indexes)
    progress("Đang chuẩn bị đo trước/sau trên lab 3309...")
    kwargs = {"query_id": query_id, "original_sql": sql,
              "rewritten_sql": rewrite or sql, "indexes": indexes,
              "fk_snapshots": snapshots, "timeout_ms": 60000, "allow_no_index": True,
              "progress": progress}
    if mode == "fast":
        report = (measure or _default_fast_measure)(**kwargs)
    else:
        if mode == "quick":
            kwargs["warmup_runs"], kwargs["measured_runs"] = QUICK_RUNS
        report = (measure or _default_measure)(**kwargs)

    return {
        **base, **{k: report.get(k) for k in (
            "status", "failure_reason", "before", "after", "index_usage",
            "mode", "measured_runs")},
        "rewrite_changed": bool(rewrite and rewrite.strip() != sql.strip()),
        "indexes": [{"table": i["table"], "index_name": i["index_name"],
                     "columns": [c["name"] for c in i.get("columns", [])]} for i in indexes],
        "greedy": greedy_summary, "elapsed_s": round(time.time() - started, 1),
    }


def _default_store_path() -> Path:
    return Path(os.getenv("DASHBOARD_STORE_PATH")
                or ROOT / "data" / "outputs" / "proposals.sqlite3")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Đo trước/sau trên validation lab 3309.")
    sub = parser.add_subparsers(dest="command", required=True)
    measure = sub.add_parser("measure")
    measure.add_argument("--request", type=Path, required=True)
    measure.add_argument("--out", type=Path, required=True)
    measure.add_argument("--store", type=Path, default=None)
    args = parser.parse_args(argv)

    progress_path = args.out.with_name("progress.json")

    def progress(stage: str) -> None:
        _write_json(progress_path, {"stage": stage, "ts": time.time()})

    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        result = run_measure(request, store_path=args.store or _default_store_path(),
                             progress=progress)
    except Exception as exc:  # noqa: BLE001 - luôn ghi kết quả để Dashboard dừng chờ
        traceback.print_exc()
        result = {"kind": "measure", "status": "error", "failure_reason": "runner_error",
                  "error_type": type(exc).__name__, "approvable": False}
    _write_json(args.out, result)
    print(json.dumps({k: result.get(k) for k in ("status", "failure_reason")}))
    return 0 if result.get("status") in ("passed", "failed", "no_proposal") else 1


if __name__ == "__main__":
    raise SystemExit(main())
