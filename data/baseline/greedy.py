"""
data/baseline/greedy.py
-----------------------

CHỨC NĂNG :
    Baseline 1 (đề xuất index): thuật toán greedy chọn index theo giảm cost từ EXPLAIN.

PHỤ TRÁCH  : Tường    |    REVIEW: Hải

THAM KHẢO  : project-management/ROADMAP.md (mục 2.5)

TRẠNG THÁI : ĐÃ CÀI ĐẶT — thuật toán greedy chọn index theo giảm EXPLAIN query_cost.
"""

import argparse
import asyncio
import json
import re
from collections.abc import Callable
from pathlib import Path

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from data.baseline.rule_based import DEFAULT_EXISTING_PREFIXES, MAX_INDEX_COLUMNS


def _make_index_name(table: str, col_names: list[str]) -> str:
    raw = f"gr_{table}_{'_'.join(col_names)}".lower()
    clean = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    return f"idx_{clean[:50]}"


def _is_redundant_prefix(
    table: str, col_names: list[str], existing_prefixes: dict[str, tuple[tuple[str, ...], ...]]
) -> bool:
    for prefix in existing_prefixes.get(table, ()):
        if len(col_names) <= len(prefix) and tuple(col_names) == prefix[: len(col_names)]:
            return True
    return False


def extract_candidate_columns(sql: str) -> dict[str, list[str]]:
    """Trích các cột xuất hiện trong WHERE, JOIN, GROUP BY, ORDER BY theo từng bảng."""
    if not isinstance(sql, str) or not sql.strip():
        return {}
    try:
        tree = parse_one(sql, read="mysql")
    except ParseError:
        return {}
    if not isinstance(tree, exp.Select):
        return {}

    alias_map: dict[str, str] = {}
    tables_in_order: list[str] = []
    for tbl in tree.find_all(exp.Table):
        real_name = (tbl.name or "").lower()
        if not real_name:
            continue
        if real_name not in tables_in_order:
            tables_in_order.append(real_name)
        alias_map[real_name] = real_name
        if tbl.alias:
            alias_map[tbl.alias.lower()] = real_name

    if not tables_in_order:
        return {}
    default_table = tables_in_order[0] if len(tables_in_order) == 1 else None

    result: dict[str, list[str]] = {table: [] for table in tables_in_order}
    clauses = [tree.args.get("where"), tree.args.get("group"), tree.args.get("order")]
    for join in tree.args.get("joins") or []:
        clauses.append(join.args.get("on"))

    for clause in clauses:
        if clause is None:
            continue
        for col in clause.find_all(exp.Column):
            qualifier = (col.table or "").lower()
            table = alias_map.get(qualifier, qualifier) if qualifier else default_table
            col_name = (col.name or "").lower()
            if table in result and col_name and col_name not in result[table]:
                result[table].append(col_name)

    return {table: cols for table, cols in result.items() if cols}


def greedy_select_indexes(
    sql: str,
    *,
    cost_evaluator: Callable[[str, list[dict]], float],
    query_id: str | None = None,
    max_columns: int = 3,
    max_indexes: int = 2,
    min_cost_improvement_pct: float = 5.0,
    existing_prefixes: dict[str, tuple[tuple[str, ...], ...]] | None = DEFAULT_EXISTING_PREFIXES,
) -> dict:
    """Chọn tập index tham lam theo mức giảm EXPLAIN query_cost.

    cost_evaluator(sql, proposals) -> query_cost (float) khi bật tập proposals.
    """
    max_cols = min(max_columns, MAX_INDEX_COLUMNS)
    candidates_by_table = extract_candidate_columns(sql)
    baseline_cost = float(cost_evaluator(sql, []))
    current_cost = baseline_cost
    selected: list[dict] = []
    prefixes = existing_prefixes or {}

    if not candidates_by_table or baseline_cost <= 0:
        return {
            "query_id": query_id,
            "baseline_cost": baseline_cost,
            "final_cost": current_cost,
            "cost_reduction_pct": 0.0,
            "proposals": [],
        }

    for _ in range(max_indexes):
        best_proposal: dict | None = None
        best_cost = current_cost

        for table, cols in candidates_by_table.items():
            # Mở rộng tham lam từ 1 cột -> max_cols cho từng bảng
            prefix: list[str] = []
            table_best_cost = current_cost
            table_best_cols: list[str] | None = None

            for _step in range(min(max_cols, len(cols))):
                step_best_col: str | None = None
                step_best_cost = table_best_cost

                for col in cols:
                    if col in prefix:
                        continue
                    trial_cols = [*prefix, col]
                    if _is_redundant_prefix(table, trial_cols, prefixes):
                        continue
                    idx_name = _make_index_name(table, trial_cols)
                    if any(p["index_name"] == idx_name for p in selected):
                        continue
                    proposal = {
                        "type": "index",
                        "table": table,
                        "columns": [{"name": c, "order": "ASC"} for c in trial_cols],
                        "index_name": idx_name,
                        "rationale": "Greedy EXPLAIN query_cost reduction",
                        "target_query_ids": [query_id] if query_id else [],
                    }
                    trial_cost = float(cost_evaluator(sql, [*selected, proposal]))
                    if trial_cost < step_best_cost:
                        step_best_cost = trial_cost
                        step_best_col = col

                if step_best_col is None:
                    break
                prefix.append(step_best_col)
                table_best_cost = step_best_cost
                table_best_cols = list(prefix)

            if table_best_cols and table_best_cost < best_cost:
                best_cost = table_best_cost
                best_proposal = {
                    "type": "index",
                    "table": table,
                    "columns": [{"name": c, "order": "ASC"} for c in table_best_cols],
                    "index_name": _make_index_name(table, table_best_cols),
                    "rationale": "Greedy EXPLAIN query_cost reduction",
                    "target_query_ids": [query_id] if query_id else [],
                }

        if best_proposal is None:
            break
        improvement_pct = (current_cost - best_cost) / current_cost * 100.0
        if improvement_pct < min_cost_improvement_pct:
            break
        selected.append(best_proposal)
        current_cost = best_cost

    total_reduction = (
        round((baseline_cost - current_cost) / baseline_cost * 100.0, 2)
        if baseline_cost > 0
        else 0.0
    )
    return {
        "query_id": query_id,
        "baseline_cost": baseline_cost,
        "final_cost": current_cost,
        "cost_reduction_pct": total_reduction,
        "proposals": selected,
    }


def make_lab_cost_evaluator() -> Callable[[str, list[dict]], float]:
    """Tạo cost_evaluator dùng TrialIndex INVISIBLE + explain_query trên lab 3309."""
    from mcp_server.tools.apply import TrialIndex
    from mcp_server.tools.explain import explain_query
    from mcp_server.utils.config import Config
    from mcp_server.utils.db import get_conn
    from mcp_server.validation.validator import _tool_data

    if Config.DB_HOST != "127.0.0.1" or Config.DB_PORT != 3309 or Config.DB_NAME != "shopdb":
        raise ValueError("greedy lab evaluator chỉ chạy trên validation lab 3309")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT marker FROM mcp_validation_lab_identity LIMIT 1")
        row = cur.fetchone()
    if not row or row.get("marker") != "mcp-validation-lab-v1":
        raise ValueError("validation lab thiếu marker hợp lệ")

    def evaluate(sql: str, proposals: list[dict]) -> float:
        started: list[TrialIndex] = []
        try:
            for prop in proposals:
                trial = TrialIndex(prop)
                snap = trial.fk_support_snapshot()
                started.append(trial)
                trial.create(fk_snapshot=snap)
            raw = asyncio.run(
                explain_query(sql, mode="estimate", use_invisible_indexes=bool(proposals))
            )
            data = _tool_data(raw)
            return float(data["query_cost"])
        finally:
            for trial in reversed(started):
                trial.drop()

    return evaluate


def evaluate_catalog(
    queries: list[dict],
    ground_truth: dict,
    *,
    cost_evaluator: Callable[[str, list[dict]], float],
    max_columns: int = 2,
    max_indexes: int = 1,
    output_path: Path | None = None,
) -> dict:
    """Chạy greedy cho 18 query nhóm Index (1, 2, 4), lưu tiến độ từng query và chấm khớp chính xác."""
    from data.metrics.metrics import INDEX_GROUPS, score_index_query

    per_query: list[dict] = []
    done_by_id: dict[str, dict] = {}
    if output_path and output_path.is_file():
        prev = json.loads(output_path.read_text(encoding="utf-8"))
        for row in prev.get("per_query", []):
            done_by_id[row["query_id"]] = row

    for item in queries:
        qid = item["id"]
        if item["group"] not in INDEX_GROUPS:
            continue
        if qid in done_by_id:
            per_query.append(done_by_id[qid])
            continue
        res = greedy_select_indexes(
            item["sql"],
            cost_evaluator=cost_evaluator,
            query_id=qid,
            max_columns=max_columns,
            max_indexes=max_indexes,
        )
        score = score_index_query(qid, res["proposals"], ground_truth)
        score["baseline_cost"] = res["baseline_cost"]
        score["final_cost"] = res["final_cost"]
        score["cost_reduction_pct"] = res["cost_reduction_pct"]
        score["proposed_indexes"] = [
            {"table": p["table"], "columns": p["columns"], "index_name": p["index_name"]}
            for p in res["proposals"]
        ]
        per_query.append(score)
        if output_path:
            summary = _build_catalog_summary(per_query)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    return _build_catalog_summary(per_query)


def _build_catalog_summary(per_query: list[dict]) -> dict:
    total_proposals = sum(item["index_proposals"] for item in per_query)
    total_exact = sum(item["exact_matches"] for item in per_query)
    queries_with_exact = sum(1 for item in per_query if item["exact_matches"] > 0)
    queries_needing_equiv = sum(1 for item in per_query if item["equivalence_needed"])
    return {
        "method": "greedy",
        "scope": "index_groups_exact_match_diagnostic",
        "index_group_query_count": len(per_query),
        "total_index_proposals": total_proposals,
        "exact_index_matches": total_exact,
        "queries_with_exact_index": queries_with_exact,
        "queries_needing_equivalence": queries_needing_equiv,
        "exact_precision": round(total_exact / total_proposals, 4) if total_proposals else 0.0,
        "exact_recall": round(queries_with_exact / len(per_query), 4) if per_query else 0.0,
        "per_query": per_query,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chạy baseline greedy theo EXPLAIN query_cost trên validation lab 3309."
    )
    parser.add_argument("query_id", nargs="?", default=None, help="ID query catalog, ví dụ: q07")
    parser.add_argument("--catalog", action="store_true", help="Chạy đủ 18 query nhóm Index (1/2/4)")
    parser.add_argument("--max-columns", type=int, default=3)
    parser.add_argument("--max-indexes", type=int, default=2)
    parser.add_argument("--output", "-o", type=Path, default=None)
    args = parser.parse_args()

    from data.queries.queries import QUERIES

    if args.catalog:
        truth_path = Path(__file__).resolve().parents[1] / "queries" / "ground_truth.json"
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        evaluator = make_lab_cost_evaluator()
        summary = evaluate_catalog(
            QUERIES,
            truth,
            cost_evaluator=evaluator,
            max_columns=args.max_columns,
            max_indexes=args.max_indexes,
            output_path=args.output,
        )
        text = json.dumps(summary, indent=2, ensure_ascii=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
            print(f"Đã lưu kết quả greedy catalog: {args.output}")
        else:
            print(text)
        return

    catalog = {item["id"]: item for item in QUERIES}
    if not args.query_id or args.query_id not in catalog:
        parser.error("cần query_id hợp lệ trong catalog (hoặc dùng --catalog)")

    evaluator = make_lab_cost_evaluator()
    result = greedy_select_indexes(
        catalog[args.query_id]["sql"],
        cost_evaluator=evaluator,
        query_id=args.query_id,
        max_columns=args.max_columns,
        max_indexes=args.max_indexes,
    )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Đã lưu kết quả greedy: {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
