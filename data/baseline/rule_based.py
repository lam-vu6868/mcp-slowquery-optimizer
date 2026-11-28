"""
data/baseline/rule_based.py
---------------------------

CHỨC NĂNG :
    Baseline 2 (đề xuất index): luật cứng equality -> range -> ORDER BY.

PHỤ TRÁCH  : Tường    |    REVIEW: Hải

THAM KHẢO  : project-management/ROADMAP.md (mục 2.5)

TRẠNG THÁI : ĐÃ CÀI ĐẶT — sinh đề xuất index theo luật E-R-S (sqlglot) và chấm khớp chính xác.
"""

import argparse
import json
import re
from pathlib import Path

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

MAX_INDEX_COLUMNS = 5

# Các tiền tố index mặc định đã có từ db/schema.sql (PK, UNIQUE, FK)
DEFAULT_EXISTING_PREFIXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "customers": (("customer_id",), ("email",)),
    "products": (("product_id",),),
    "addresses": (("address_id",), ("customer_id",)),
    "orders": (("order_id",), ("customer_id",)),
    "order_items": (("order_item_id",), ("order_id",), ("product_id",)),
}


def _is_constant(node: exp.Expression | None) -> bool:
    """Kiểm tra biểu thức là hằng số (không chứa cột của bảng)."""
    if node is None:
        return False
    return not any(node.find_all(exp.Column))


def _resolve_table(
    col: exp.Column, alias_map: dict[str, str], default_table: str | None
) -> str | None:
    qualifier = (col.table or "").lower()
    if qualifier:
        return alias_map.get(qualifier, qualifier)
    return default_table


def _is_redundant_prefix(
    table: str, col_names: list[str], existing_prefixes: dict[str, tuple[tuple[str, ...], ...]]
) -> bool:
    for prefix in existing_prefixes.get(table, ()):
        if len(col_names) <= len(prefix) and tuple(col_names) == prefix[: len(col_names)]:
            return True
    return False


def _make_index_name(table: str, col_names: list[str]) -> str:
    raw = f"rb_{table}_{'_'.join(col_names)}".lower()
    clean = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    return f"idx_{clean[:50]}"


def propose_indexes(
    sql: str,
    *,
    query_id: str | None = None,
    max_columns: int = MAX_INDEX_COLUMNS,
    existing_prefixes: dict[str, tuple[tuple[str, ...], ...]] | None = DEFAULT_EXISTING_PREFIXES,
) -> list[dict]:
    """Đề xuất index theo luật cứng equality -> range -> ORDER BY cho một câu SELECT."""
    if not isinstance(sql, str) or not sql.strip():
        return []
    try:
        tree = parse_one(sql, read="mysql")
    except ParseError:
        return []
    if not isinstance(tree, exp.Select):
        return []

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
        return []
    default_table = tables_in_order[0] if len(tables_in_order) == 1 else None

    eq_cols: dict[str, list[str]] = {}
    range_cols: dict[str, list[str]] = {}
    order_cols: dict[str, list[tuple[str, str]]] = {}

    def _add_unique(bucket: dict[str, list[str]], table: str | None, col_name: str) -> None:
        if not table or not col_name:
            return
        cols = bucket.setdefault(table, [])
        if col_name not in cols:
            cols.append(col_name)

    where = tree.args.get("where")
    if where is not None:
        # 1. Equality: col = literal | literal = col | col IN (literals)
        for node in where.find_all(exp.EQ):
            left, right = node.this, node.expression
            if isinstance(left, exp.Column) and _is_constant(right):
                _add_unique(eq_cols, _resolve_table(left, alias_map, default_table), left.name.lower())
            elif isinstance(right, exp.Column) and _is_constant(left):
                _add_unique(eq_cols, _resolve_table(right, alias_map, default_table), right.name.lower())

        for node in where.find_all(exp.In):
            target = node.this
            exprs = node.expressions
            if isinstance(target, exp.Column) and exprs and all(_is_constant(e) for e in exprs):
                _add_unique(eq_cols, _resolve_table(target, alias_map, default_table), target.name.lower())

        # 2. Range: >, >=, <, <=, BETWEEN
        for node in where.find_all((exp.GT, exp.GTE, exp.LT, exp.LTE)):
            left, right = node.this, node.expression
            if isinstance(left, exp.Column) and _is_constant(right):
                _add_unique(range_cols, _resolve_table(left, alias_map, default_table), left.name.lower())
            elif isinstance(right, exp.Column) and _is_constant(left):
                _add_unique(range_cols, _resolve_table(right, alias_map, default_table), right.name.lower())

        for node in where.find_all(exp.Between):
            target = node.this
            if (
                isinstance(target, exp.Column)
                and _is_constant(node.args.get("low"))
                and _is_constant(node.args.get("high"))
            ):
                _add_unique(range_cols, _resolve_table(target, alias_map, default_table), target.name.lower())

    # 3. ORDER BY (chỉ cột trực tiếp, giữ hướng ASC/DESC)
    order = tree.args.get("order")
    if order is not None:
        for ordered in order.expressions:
            target = ordered.this
            if isinstance(target, exp.Column):
                table = _resolve_table(target, alias_map, default_table)
                if table:
                    direction = "DESC" if ordered.args.get("desc") else "ASC"
                    cols = order_cols.setdefault(table, [])
                    col_name = target.name.lower()
                    if all(existing != col_name for existing, _ in cols):
                        cols.append((col_name, direction))

    proposals: list[dict] = []
    prefixes = existing_prefixes or {}
    for table in tables_in_order:
        combined: list[tuple[str, str]] = []
        seen: set[str] = set()
        for col in eq_cols.get(table, []):
            if col not in seen:
                combined.append((col, "ASC"))
                seen.add(col)
        for col in range_cols.get(table, []):
            if col not in seen:
                combined.append((col, "ASC"))
                seen.add(col)
        for col, direction in order_cols.get(table, []):
            if col not in seen:
                combined.append((col, direction))
                seen.add(col)

        combined = combined[:max_columns]
        if not combined:
            continue
        col_names = [name for name, _ in combined]
        if _is_redundant_prefix(table, col_names, prefixes):
            continue
        proposals.append({
            "type": "index",
            "table": table,
            "columns": [{"name": name, "order": direction} for name, direction in combined],
            "index_name": _make_index_name(table, col_names),
            "rationale": "Rule-based E-R-S (equality -> range -> ORDER BY)",
            "target_query_ids": [query_id] if query_id else [],
        })
    return proposals


def evaluate_catalog(queries: list[dict], ground_truth: dict) -> dict:
    """Chạy rule-based trên các query nhóm index (1, 2, 4) và chấm khớp chính xác."""
    from data.metrics.metrics import INDEX_GROUPS, score_index_query

    per_query: list[dict] = []
    total_proposals = 0
    total_exact = 0
    queries_with_exact = 0
    queries_needing_equiv = 0

    for item in queries:
        qid = item["id"]
        if item["group"] not in INDEX_GROUPS:
            continue
        proposals = propose_indexes(item["sql"], query_id=qid)
        score = score_index_query(qid, proposals, ground_truth)
        score["proposed_indexes"] = [
            {"table": p["table"], "columns": p["columns"], "index_name": p["index_name"]}
            for p in proposals
        ]
        per_query.append(score)
        total_proposals += score["index_proposals"]
        total_exact += score["exact_matches"]
        if score["exact_matches"] > 0:
            queries_with_exact += 1
        if score["equivalence_needed"]:
            queries_needing_equiv += 1

    return {
        "method": "rule_based",
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
        description="Chạy baseline rule-based (equality -> range -> ORDER BY) trên catalog."
    )
    parser.add_argument("--output", "-o", type=Path, default=None, help="File JSON lưu kết quả")
    args = parser.parse_args()

    from data.queries.queries import QUERIES

    truth_path = Path(__file__).resolve().parents[1] / "queries" / "ground_truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    summary = evaluate_catalog(QUERIES, truth)
    text = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Đã lưu kết quả rule-based: {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
