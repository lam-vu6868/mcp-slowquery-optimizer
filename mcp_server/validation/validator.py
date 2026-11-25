"""
mcp_server/validation/validator.py
----------------------------------

CHỨC NĂNG :
    Validation Layer chính: kiểm chứng đề xuất TRƯỚC khi cho người duyệt.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Quy trình: tạo index INVISIBLE -> đo 'trước' (không bật cờ) -> đo 'sau' (SET SESSION optimizer_switch='use_invisible_indexes=on') -> so sánh -> ghi validation_report.
    - Pass khi: đủ lượt đo, hash tương đương, P95 giảm >= 20%, index được EXPLAIN dùng và không lỗi/timeout.
    - Fail hoặc inconclusive: gọi helper DDL nội bộ để dọn index thử; không phát approval token.
    - Đo write overhead trên clone; ước lượng dung lượng index bằng chênh lệch TABLES.INDEX_LENGTH.
    - Ngưỡng lấy từ config/settings.yaml.

THAM KHẢO  : docs/api-contract.md (mục 4), project-management/ROADMAP.md (mục 2.3)

TRẠNG THÁI : ĐANG LÀM — luồng index chính test bằng DB giả; chi phí ghi đã đo mẫu trên write lab thật.
"""

import json
import math
from pathlib import Path

import yaml
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from security.ast_whitelist import check as ast_check


def _settings() -> dict:
    path = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)["validation"]
    if (type(data.get("warmup_runs")) is not int or data["warmup_runs"] < 0
            or type(data.get("measured_runs")) is not int
            or not 20 <= data["measured_runs"] <= 50
            or type(data.get("min_p95_improvement_pct")) not in (int, float)
            or not 20 <= data["min_p95_improvement_pct"] <= 100
            or data.get("require_result_equivalence") is not True
            or type(data.get("write_overhead_rows")) is not int
            or data["write_overhead_rows"] < 1):
        raise ValueError("validation settings không hợp lệ hoặc làm yếu ngưỡng")
    return data


def _number(value: object, *, positive: bool = False) -> bool:
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def _measurement_complete(item: object, required_runs: int, *, before: bool) -> bool:
    if not isinstance(item, dict):
        return False
    return (
        _number(item.get("p95_ms"), positive=before)
        and _number(item.get("query_cost"))
        and type(item.get("rows_examined")) is int and item["rows_examined"] >= 0
        and isinstance(item.get("result_hash"), str) and bool(item["result_hash"])
        and type(item.get("row_count")) is int and item["row_count"] >= 0
        and type(item.get("runs")) is int and item["runs"] >= required_runs
        and type(item.get("timed_out_runs")) is int and item["timed_out_runs"] == 0
    )


def _write_evidence_complete(item: object, required_rows: int) -> bool:
    if not isinstance(item, dict):
        return False
    throughput = item.get("insert_throughput_change_pct")
    before_rate = item.get("before_rows_per_second")
    after_rate = item.get("after_rows_per_second")
    return (
        type(throughput) in (int, float) and math.isfinite(throughput)
        and _number(before_rate, positive=True)
        and _number(after_rate, positive=True)
        and abs(throughput - (after_rate / before_rate - 1) * 100) <= 0.1
        and type(item.get("sample_rows")) is int
        and item["sample_rows"] == required_rows
        and type(item.get("preload_rows")) is int
        and item["preload_rows"] == required_rows
        and _number(item.get("index_size_bytes"), positive=True)
        and item.get("index_size_source") == "table_index_length_delta"
        and item.get("index_size_estimated") is True
        and item.get("measurement_scope") == "isolated_lab"
    )


def _plan_uses_index(raw_plan: object, sql: str, table_name: str,
                     index_name: str) -> bool:
    """Tìm index trên đúng bảng, kể cả khi bảng nằm sau trong JOIN."""
    if not isinstance(raw_plan, dict):
        return False
    try:
        parsed = parse_one(sql, read="mysql")
    except (ParseError, TypeError, ValueError):
        return False
    if parsed is None:
        return False
    tables = list(parsed.find_all(exp.Table))
    aliases = {table.alias_or_name for table in tables if table.name == table_name}
    # An alias reused for another table in a nested scope cannot identify
    # the plan node unambiguously; fail closed instead of proving the wrong index.
    aliases -= {table.alias_or_name for table in tables if table.name != table_name}
    if not aliases:
        return False

    def walks(node: object) -> bool:
        if isinstance(node, list):
            return any(walks(item) for item in node)
        if not isinstance(node, dict):
            return False
        table = node.get("table")
        if (isinstance(table, dict) and table.get("table_name") in aliases
                and table.get("key") == index_name):
            return True
        return any(walks(value) for value in node.values())

    return walks(raw_plan)


def assess_index_report(
    report: dict, *, expected_index_name: str,
    expected_table: str, original_sql: str,
    required_runs: int | None = None, min_improvement_ratio: float | None = None,
) -> dict:
    """Đánh giá bằng chứng index mà không đụng DB hoặc tin trạng thái caller gửi."""
    settings = _settings()
    if required_runs is None:
        required_runs = settings["measured_runs"]
    if min_improvement_ratio is None:
        min_improvement_ratio = settings["min_p95_improvement_pct"] / 100
    if type(required_runs) is not int or required_runs < settings["measured_runs"]:
        raise ValueError("required_runs không được thấp hơn config")
    if (not _number(min_improvement_ratio)
            or not settings["min_p95_improvement_pct"] / 100 <= min_improvement_ratio <= 1):
        raise ValueError("min_improvement_ratio không được thấp hơn config")
    if not isinstance(expected_index_name, str) or not expected_index_name:
        raise ValueError("expected_index_name không được rỗng")

    result = dict(report)
    result.update(status="inconclusive", evidence_complete=False,
                  result_equivalent=None, improvement_ratio=None,
                  failure_reason="measurement_incomplete")
    if (report.get("candidate_sql_kind") != "original"
            or not report.get("proposal_id") or not report.get("query_id")):
        result["failure_reason"] = "proposal_context_invalid"
        return result
    before, after = report.get("before"), report.get("after")
    if not (_measurement_complete(before, required_runs, before=True)
            and _measurement_complete(after, required_runs, before=False)):
        return result

    same = (before["result_hash"] == after["result_hash"]
            and before["row_count"] == after["row_count"])
    gain = (before["p95_ms"] - after["p95_ms"]) / before["p95_ms"]
    result.update(result_equivalent=same, improvement_ratio=gain)
    index_used = (after.get("key_used") == expected_index_name
                  and _plan_uses_index(after.get("raw_plan"), original_sql,
                                       expected_table, expected_index_name))
    write_complete = _write_evidence_complete(
        report.get("write_overhead"), settings["write_overhead_rows"],
    )
    result["evidence_complete"] = index_used and write_complete

    if not same:
        result.update(status="failed", failure_reason="result_changed")
    elif gain < min_improvement_ratio:
        result.update(status="failed", failure_reason="p95_below_threshold")
    elif not index_used:
        result["failure_reason"] = "index_not_used"
    elif not write_complete:
        result["failure_reason"] = "write_evidence_incomplete"
    else:
        result.update(status="passed", failure_reason=None)
    return result


def _tool_data(response: str) -> dict:
    envelope = json.loads(response)
    if not isinstance(envelope, dict) or envelope.get("ok") is not True:
        raise ValueError("tool_measurement_failed")
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise TypeError("tool_data_missing")
    return data


async def validate_index(
    *, proposal_id: str, query_id: str, original_sql: str, index_name: str,
    target_table: str,
    create_trial, drop_trial, measure_size, measure_write,
    explain=None, benchmark=None,
) -> dict:
    """Đo index trên SQL gốc; DDL và đo ghi do backend cấp, không nhận DDL tự do."""
    if explain is None:
        from mcp_server.tools.explain import explain_query as explain
    if benchmark is None:
        from mcp_server.tools.benchmark import benchmark_query as benchmark
    settings = _settings()

    report = {
        "proposal_id": proposal_id, "query_id": query_id,
        "candidate_sql_kind": "original", "before": None, "after": None,
        "write_overhead": None,
    }
    ok, _ = ast_check(original_sql)
    if not ok:
        return {**assess_index_report(report, expected_index_name=index_name,
                                      expected_table=target_table,
                                      original_sql=original_sql),
                "failure_reason": "ast_rejected"}

    trial_started = False
    try:
        trial_started = True
        create_trial()
        for label, enabled in (("before", False), ("after", True)):
            plan = _tool_data(await explain(
                original_sql, mode="estimate", use_invisible_indexes=enabled,
            ))
            measurement = _tool_data(await benchmark(
                original_sql, warmup_runs=settings["warmup_runs"],
                measured_runs=settings["measured_runs"],
                use_invisible_indexes=enabled, compute_result_hash=True,
            ))
            cost = plan.get("query_cost")
            try:
                cost = float(cost) if cost is not None else None
            except (TypeError, ValueError):
                cost = None
            report[label] = {**measurement, "query_cost": cost}
            if enabled:
                raw_plan = plan.get("raw_plan")
                report[label]["raw_plan"] = raw_plan
                report[label]["key_used"] = (
                    index_name if _plan_uses_index(
                        raw_plan, original_sql, target_table, index_name,
                    ) else plan.get("key_used")
                )

        size = measure_size()
        write_measurement = measure_write()
        report["write_overhead"] = {
            **(write_measurement if isinstance(write_measurement, dict) else {}),
            "index_size_bytes": size,
            "index_size_source": "table_index_length_delta",
            "index_size_estimated": True,
        }
        result = assess_index_report(
            report, expected_index_name=index_name,
            expected_table=target_table, original_sql=original_sql,
        )
    except Exception:  # noqa: BLE001 - always attempt cleanup after DB/tool failures
        result = assess_index_report(
            report, expected_index_name=index_name,
            expected_table=target_table, original_sql=original_sql,
        )
        result["failure_reason"] = "measurement_error"

    if trial_started and result["status"] != "passed":
        try:
            drop_trial()
        except Exception:  # noqa: BLE001 - retain explicit cleanup failure in report
            result.update(status="inconclusive", evidence_complete=False,
                          failure_reason="cleanup_failed")
    return result


async def validate_saved_index(
    store, proposal_id: str, *, measure_write=None, write_csv_dir=None,
    trial_factory=None, explain=None, benchmark=None,
) -> dict:
    """Đường nội bộ: lấy SQL/proposal đã lưu, đo và lưu report đúng một lần."""
    if trial_factory is None:
        from mcp_server.tools.apply import TrialIndex as trial_factory
    saved = store.get(proposal_id)
    if measure_write is None:
        if write_csv_dir is None:
            raise ValueError("cần write_csv_dir để đo chi phí ghi trên lab riêng")
        from mcp_server.validation.write_overhead import measure_insert_overhead

        def measure_write():
            return measure_insert_overhead(saved["proposal"], csv_dir=write_csv_dir)

    trial = trial_factory(saved["proposal"], proposal_id=proposal_id)
    store.begin_trial(proposal_id)
    result = await validate_index(
        proposal_id=proposal_id, query_id=saved["query_id"],
        original_sql=saved["original_sql"],
        index_name=saved["proposal"]["index_name"],
        target_table=saved["proposal"]["table"],
        create_trial=trial.create, drop_trial=trial.drop,
        measure_size=trial.size_delta, measure_write=measure_write,
        explain=explain, benchmark=benchmark,
    )
    try:
        return store.save_report(proposal_id, result)
    except Exception:
        if result["status"] == "passed":
            trial.drop()
        raise
