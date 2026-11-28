"""Đo offline SQL rewrite với toàn bộ index LLM trên lab được phép.
PHỤ TRÁCH: Vũ | REVIEW: Hải.
LƯU Ý: CLI --dry-run chỉ chạy load + preflight (không tạo DDL).
       Report này chỉ dùng cho metric rewrite, không cấp token Tool 6.
THAM KHẢO: docs/api-contract.md mục 2.2, ROADMAP mục 2.4.

Chạy (dry-run, không DDL):
    python -m scripts.measure_llm_rewrite q14 data/outputs/llm_catalog_20261127/q14.sqlite3 --dry-run
Chạy thật (cần lab 3309 đang chạy, marker hợp lệ):
    python -m scripts.measure_llm_rewrite q14 data/outputs/llm_catalog_20261127/q14.sqlite3
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from mcp_server.store.proposals import ProposalStore
from mcp_server.tools.apply import TrialIndex
from mcp_server.utils.config import Config
from mcp_server.utils.db import get_conn
from mcp_server.validation.validator import (
    _measurement_complete,
    _plan_uses_index,
    _settings,
    _tool_data,
)
from security.ast_whitelist import check as ast_check

# ---------------------------------------------------------------------------
# 1. Loader: đọc proposal từ SQLite đã lưu
# ---------------------------------------------------------------------------

def load_saved_rewrite(path: str | Path, query_id: str, catalog_sql: str) -> dict:
    """Đọc đúng một rewrite và mọi index của query; không tạo SQLite rỗng."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("store proposal không tồn tại")
    saved = [item for item in ProposalStore(path).recent_proposals()
             if item["query_id"] == query_id]
    if (not saved or any(item["original_sql"] != catalog_sql
                         or item["trial_state"] != "new" for item in saved)):
        raise ValueError("proposal không khớp catalog hoặc đã dùng trial")
    rewrites = [item["proposal"] for item in saved
                if item["proposal"].get("type") == "rewrite"]
    indexes = [item["proposal"] for item in saved
               if item["proposal"].get("type") == "index"]
    if len(rewrites) != 1 or not indexes or len(rewrites) + len(indexes) != len(saved):
        raise ValueError("cần đúng một rewrite và ít nhất một index")
    rewritten_sql = rewrites[0].get("rewritten_sql")
    if (rewrites[0].get("original_query_id") != query_id
            or not ast_check(catalog_sql)[0]
            or not isinstance(rewritten_sql, str)
            or not ast_check(rewritten_sql)[0]):
        raise ValueError("SQL rewrite hoặc query_id không hợp lệ")
    for index in indexes:
        TrialIndex(index)  # chỉ kiểm cấu trúc, chưa tạo index
    return {"query_id": query_id, "original_sql": catalog_sql,
            "rewritten_sql": rewritten_sql, "indexes": indexes}


# ---------------------------------------------------------------------------
# 2. Preflight: kiểm marker + snapshot FK/index (chỉ đọc, không DDL)
# ---------------------------------------------------------------------------

def preflight_validation_lab(indexes: list[dict], *, trial_factory=TrialIndex,
                             marker_reader=None) -> dict:
    """Chỉ đọc marker và snapshot trên lab 3309 trước khi cân nhắc DDL."""
    if (Config.DB_HOST != "127.0.0.1" or Config.DB_PORT != 3309
            or Config.DB_NAME != "shopdb" or Config.DB_USER != "readonly_user"
            or Config.DB_ADMIN_USER != "index_admin"):
        raise ValueError("chỉ được preflight validation lab 3309")
    if marker_reader is None:
        def marker_reader():
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute("SELECT marker FROM mcp_validation_lab_identity LIMIT 1")
                row = cur.fetchone()
            return row.get("marker") if row else None
    if marker_reader() != "mcp-validation-lab-v1":
        raise ValueError("validation lab thiếu marker hợp lệ")
    if not indexes:
        raise ValueError("thiếu index để kiểm")
    snapshots = {}
    for proposal in indexes:
        trial = trial_factory(proposal)
        snapshot = trial.fk_support_snapshot()
        # Truyền snapshot vào _check_schema để nhánh FK opt-in được phép;
        # nếu cần recovery thêm điều kiện khác thì _check_schema sẽ raise.
        trial._check_schema(fk_snapshot=snapshot)
        snapshots[proposal["index_name"]] = snapshot
    return snapshots


def save_preflight_snapshot(snapshot_path: str | Path, query_id: str,
                            snapshots: dict) -> None:
    """Ghi snapshot FK/index ra file JSON bền vững trước bước DDL.

    Snapshot được ghi trước khi tạo bất kỳ trial nào; dùng để so sánh
    và kiểm tra cleanup sau khi đo xong. Caller phải đọc lại file này
    để xác nhận khớp trước khi kết luận cleanup thành công.
    File bị ghi đè nếu đã tồn tại từ lần chạy trước (vì snapshot phải
    phản ánh trạng thái hiện tại của lab, không phải trạng thái cũ).
    """
    path = Path(snapshot_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "query_id": query_id,
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "snapshots": snapshots,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_preflight_snapshot(snapshot_path: str | Path, query_id: str) -> dict:
    """Đọc lại snapshot đã lưu; kiểm query_id khớp trước khi trả."""
    path = Path(snapshot_path)
    if not path.is_file():
        raise FileNotFoundError("snapshot chưa được lưu")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("query_id") != query_id:
        raise ValueError("snapshot không khớp query_id")
    return data["snapshots"]


# ---------------------------------------------------------------------------
# 3. Phép đo chính: tạo index INVISIBLE → đo gốc/OFF & rewrite/ON → dọn
# ---------------------------------------------------------------------------

async def measure_rewrite_with_indexes(
    *, query_id: str, original_sql: str, rewritten_sql: str,
    indexes: list[dict], trial_factory, fk_snapshots: dict | None = None,
    explain=None, benchmark=None, timeout_ms: int | None = None,
) -> dict:
    """Đo SQL gốc/OFF rồi rewrite/ON; luôn dọn mọi trial đã bắt đầu.

    fk_snapshots: dict {index_name -> snapshot} từ preflight (truyền vào khi
    index có FK risk để nhánh opt-in hoạt động đúng).
    timeout_ms: giới hạn timeout cho mỗi lượt benchmark (1000-60000 ms).
    """
    report = {
        "query_id": query_id, "candidate_sql_kind": "rewritten",
        "status": "inconclusive", "failure_reason": None,
        "approvable": False, "before": None, "after": None, "index_usage": {},
    }
    if (not query_id or not indexes or not all(isinstance(item, dict)
            and item.get("table") and item.get("index_name") for item in indexes)
            or len({(item["table"], item["index_name"]) for item in indexes}) != len(indexes)
            or (timeout_ms is not None
                and (type(timeout_ms) is not int or not 1000 <= timeout_ms <= 60000))):
        report["failure_reason"] = "proposal_context_invalid"
        return report
    if not ast_check(original_sql)[0] or not ast_check(rewritten_sql)[0]:
        report["failure_reason"] = "ast_rejected"
        return report

    if explain is None:
        from mcp_server.tools.explain import explain_query as explain
    if benchmark is None:
        from mcp_server.tools.benchmark import benchmark_query as benchmark
    settings = _settings()
    started = []
    try:
        for proposal in indexes:
            trial = trial_factory(proposal)
            started.append(trial)  # create() có thể tạo index rồi mới báo lỗi
            snap = (fk_snapshots or {}).get(proposal["index_name"])
            trial.create(fk_snapshot=snap)

        for label, sql, enabled in (("before", original_sql, False),
                                    ("after", rewritten_sql, True)):
            plan = _tool_data(await explain(
                sql, mode="estimate", use_invisible_indexes=enabled,
            ))
            bench_kwargs = {
                "warmup_runs": settings["warmup_runs"],
                "measured_runs": settings["measured_runs"],
                "use_invisible_indexes": enabled,
                "compute_result_hash": True,
            }
            if timeout_ms is not None:
                bench_kwargs["timeout_ms"] = timeout_ms
            measured = _tool_data(await benchmark(sql, **bench_kwargs))
            report[label] = {
                **measured, "query_cost": float(plan["query_cost"]),
            }
            if enabled:
                report["index_usage"] = {
                    item["index_name"]: _plan_uses_index(
                        plan.get("raw_plan"), rewritten_sql,
                        item["table"], item["index_name"],
                    ) for item in indexes
                }

        before, after = report["before"], report["after"]
        if not all(_measurement_complete(item, settings["measured_runs"], before=label)
                   for item, label in ((before, True), (after, False))):
            report["failure_reason"] = "measurement_incomplete"
        elif (before["result_hash"] != after["result_hash"]
              or before["row_count"] != after["row_count"]):
            report.update(status="failed", failure_reason="result_changed")
        elif ((before["p95_ms"] - after["p95_ms"]) / before["p95_ms"]
              < settings["min_p95_improvement_pct"] / 100):
            report.update(status="failed", failure_reason="p95_below_threshold")
        else:
            report["status"] = "passed"
    except Exception as exc:  # noqa: BLE001 - cleanup cả khi tool/DDL lỗi
        report["failure_reason"] = "measurement_error"
        report["error_type"] = type(exc).__name__
    finally:
        for trial in reversed(started):
            try:
                trial.drop()
            except Exception:  # noqa: BLE001 - không che lỗi cleanup
                report.update(status="inconclusive", failure_reason="cleanup_failed")
    return report


# ---------------------------------------------------------------------------
# 4. CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Đo offline SQL rewrite + tập index LLM trên validation lab 3309. "
            "--dry-run chỉ chạy load + preflight và lưu snapshot, không tạo DDL."
        ),
    )
    parser.add_argument("query_id", help="ID query catalog, ví dụ: q14")
    parser.add_argument(
        "store_path",
        help="Đường dẫn SQLite chứa proposal LLM, ví dụ: data/outputs/llm_catalog_20261127/q14.sqlite3",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="File JSON để ghi report (mặc định: in ra stdout)",
    )
    parser.add_argument(
        "--snapshot", "-s",
        default=None,
        help="File JSON để lưu snapshot FK/index trước DDL (mặc định: <store_path>.snapshot.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ chạy load + preflight + lưu snapshot; không tạo/xóa index",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=None,
        help="Giới hạn timeout mỗi lượt benchmark (1000-60000 ms, mặc định 30000)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    store_path = Path(args.store_path)
    snapshot_path = Path(args.snapshot) if args.snapshot else store_path.with_suffix(".snapshot.json")

    # Bước 1: đọc catalog SQL
    from data.queries.queries import QUERIES
    catalog = {item["id"]: item for item in QUERIES}
    if args.query_id not in catalog:
        parser.error(f"query_id '{args.query_id}' không có trong catalog")
    catalog_sql = catalog[args.query_id]["sql"]

    # Bước 2: load proposal đã lưu
    try:
        loaded = load_saved_rewrite(store_path, args.query_id, catalog_sql)
    except (FileNotFoundError, ValueError) as err:
        parser.error(str(err))

    # Bước 3: preflight + lưu snapshot
    try:
        snapshots = preflight_validation_lab(loaded["indexes"])
    except ValueError as err:
        parser.error(str(err))

    save_preflight_snapshot(snapshot_path, args.query_id, snapshots)

    if args.dry_run:
        result = {
            "query_id": args.query_id,
            "status": "dry_run",
            "indexes": [i["index_name"] for i in loaded["indexes"]],
            "snapshot_path": str(snapshot_path),
            "approvable": False,
        }
    else:
        # Bước 4: đo thật — truyền snapshot vào trial để nhánh FK opt-in hoạt động
        result = asyncio.run(measure_rewrite_with_indexes(
            query_id=loaded["query_id"],
            original_sql=loaded["original_sql"],
            rewritten_sql=loaded["rewritten_sql"],
            indexes=loaded["indexes"],
            trial_factory=TrialIndex,
            fk_snapshots=snapshots,
            timeout_ms=args.timeout_ms,
        ))
        result["snapshot_path"] = str(snapshot_path)

    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output_json + "\n", encoding="utf-8")
        print(f"Report đã lưu: {args.output}")
    else:
        print(output_json)

    if result.get("status") not in ("passed", "dry_run"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
