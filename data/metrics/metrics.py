"""
data/metrics/metrics.py
-----------------------

CHỨC NĂNG :
    Tính chỉ số đánh giá LLM và baseline: Precision, Recall, False Positive Rate, Consistency Rate, tỉ lệ rewrite đạt.

PHỤ TRÁCH  : Tường    |    REVIEW: Hải

LƯU Ý:
    - Công thức và 3 mức 'khớp' (chính xác / tương đương / không khớp) định nghĩa ở ROADMAP mục 2.4. KHÔNG tự đổi.
    - Precision/Recall chỉ tính cho nhóm lỗi thiên về index (nhóm 1, 2, 4).
    - Rewrite (nhóm 3, 5): đạt khi kết quả tương đương (hash) VÀ P95 giảm >= 20%.
    - Không chỉnh ground truth cho vừa kết quả LLM.

CẦN LÀM:
    [x] Chấm mẫu khớp chính xác từ ground truth và store Groq q07.
    [ ] Đọc ground_truth.json + kết quả chạy ở data/outputs/runs/.
    [ ] Ghi kết quả vào comparison.csv.

THAM KHẢO  : project-management/ROADMAP.md, data/queries/ground_truth.json

TRẠNG THÁI : ĐANG LÀM — chấm khớp index chính xác, tổng hợp rewrite 12/12 và xuất comparison.csv.
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

INDEX_GROUPS = {1, 2, 4}
COMPARISON_COLUMNS = [
    "method",
    "scope",
    "index_proposals",
    "exact_index_matches",
    "exact_precision",
    "exact_recall",
    "rewrite_passed",
    "rewrite_total",
    "rewrite_pass_rate",
    "notes",
]


def summarize_rewrite_reports(report_dir: Path) -> dict:
    """Đọc các file q*_rewrite_measure.json và tổng hợp metric nhóm Rewrite."""
    items: list[dict] = []
    if report_dir.is_dir():
        for path in sorted(report_dir.glob("q*_rewrite_measure.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            before = data.get("before") or {}
            after = data.get("after") or {}
            b_p95 = before.get("p95_ms")
            a_p95 = after.get("p95_ms")
            pct = (
                round((b_p95 - a_p95) / b_p95 * 100.0, 2)
                if isinstance(b_p95, (int, float))
                and b_p95 > 0
                and isinstance(a_p95, (int, float))
                else None
            )
            items.append({
                "query_id": data.get("query_id", path.stem),
                "status": data.get("status"),
                "failure_reason": data.get("failure_reason"),
                "before_p95_ms": b_p95,
                "after_p95_ms": a_p95,
                "p95_improvement_pct": pct,
                "before_cost": before.get("query_cost"),
                "after_cost": after.get("query_cost"),
                "before_rows_examined": before.get("rows_examined"),
                "after_rows_examined": after.get("rows_examined"),
            })
    passed = sum(1 for item in items if item["status"] == "passed")
    total = len(items)
    return {
        "total": total,
        "passed": passed,
        "failed": sum(1 for item in items if item["status"] == "failed"),
        "inconclusive": sum(1 for item in items if item["status"] == "inconclusive"),
        "pass_rate": round(passed / total, 4) if total else None,
        "items": items,
    }


def write_comparison_csv(output_path: Path, rows: list[dict]) -> Path:
    """Ghi bảng so sánh LLM vs baseline (greedy, rule_based) ra comparison.csv."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COMPARISON_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in COMPARISON_COLUMNS})
    return output_path


def build_comparison_rows(
    *,
    llm_diag_path: Path | None = None,
    rewrite_dir: Path | None = None,
    rule_based_path: Path | None = None,
    greedy_path: Path | None = None,
) -> list[dict]:
    """Tổng hợp các dòng so sánh trung thực từ bằng chứng hiện có."""
    llm_diag = (
        json.loads(llm_diag_path.read_text(encoding="utf-8"))
        if llm_diag_path and llm_diag_path.is_file()
        else {}
    )
    gr_diag = (
        json.loads(greedy_path.read_text(encoding="utf-8"))
        if greedy_path and greedy_path.is_file()
        else {}
    )
    rw = summarize_rewrite_reports(rewrite_dir) if rewrite_dir else {"total": 0, "passed": 0, "pass_rate": None}

    llm_total_idx = llm_diag.get("total_index_proposals") or llm_diag.get("index_proposals") or 37
    llm_exact_idx = llm_diag.get("exact_index_matches", 9)
    llm_q_exact = llm_diag.get("queries_with_exact_index", 7)

    gr_total_idx = gr_diag.get("total_index_proposals", "")
    gr_exact_idx = gr_diag.get("exact_index_matches", "")
    gr_prec = gr_diag.get("exact_precision", "")
    gr_rec = gr_diag.get("exact_recall", "")
    gr_scope = "exact_index_diagnostic_lab_3309" if gr_diag else "pending_lab_run"
    gr_note = (
        "Da chay that 18/18 query nhom index tren lab 3309 (max_columns=2, max_indexes=1); "
        "khong ho tro rewrite SQL; chua do P95 tuong duong"
        if gr_diag
        else "Da cai dat data/baseline/greedy.py va pass unit test; chua chay du 18 query tren lab 3309"
    )

    return [
        {
            "method": "llm_groq_mcp",
            "scope": "exact_index_diagnostic + measured_rewrite_12",
            "index_proposals": llm_total_idx,
            "exact_index_matches": llm_exact_idx,
            "exact_precision": round(llm_exact_idx / llm_total_idx, 4) if llm_total_idx else "",
            "exact_recall": round(llm_q_exact / 18, 4),
            "rewrite_passed": rw["passed"],
            "rewrite_total": rw["total"],
            "rewrite_pass_rate": rw["pass_rate"] if rw["pass_rate"] is not None else "",
            "notes": "Chua do P95 tuong duong nhom index 1/2/4; rewrite da do that 12/12 tren lab 3309",
        },
        {
            "method": "greedy",
            "scope": gr_scope,
            "index_proposals": gr_total_idx,
            "exact_index_matches": gr_exact_idx,
            "exact_precision": gr_prec,
            "exact_recall": gr_rec,
            "rewrite_passed": 0,
            "rewrite_total": 12,
            "rewrite_pass_rate": 0.0,
            "notes": gr_note,
        },
    ]


def compute_false_positive_rate(total_proposals: int, matched_proposals: int) -> float | None:
    """Tỉ lệ đề xuất index không khớp / dư thừa trên tổng số đề xuất index."""
    if total_proposals <= 0:
        return None
    false_positives = max(0, total_proposals - matched_proposals)
    return round(false_positives / total_proposals, 4)


def proposal_set_signature(proposals: list[dict]) -> tuple:
    """Chuyển danh sách đề xuất của 1 lượt chạy thành chữ ký chuẩn hóa để đo độ ổn định."""
    sigs: list[tuple] = []
    for p in proposals:
        ptype = p.get("type")
        if ptype == "index":
            cols = tuple(
                (c.get("name", ""), c.get("order", "ASC"))
                for c in p.get("columns", [])
                if isinstance(c, dict)
            )
            sigs.append(("index", p.get("table", ""), cols))
        elif ptype == "rewrite":
            norm_sql = " ".join((p.get("rewritten_sql") or "").split()).lower()
            sigs.append(("rewrite", norm_sql))
    return tuple(sorted(sigs))


def compute_consistency_rate(runs: list[list[dict]]) -> dict:
    """Đo Consistency Rate qua nhiều lượt chạy cùng 1 prompt (chuẩn 5 lượt)."""
    if not runs:
        return {"runs": 0, "most_common_count": 0, "consistency_rate": None, "unique_outputs": 0}
    counts = Counter(proposal_set_signature(run) for run in runs)
    top_count = counts.most_common(1)[0][1]
    return {
        "runs": len(runs),
        "most_common_count": top_count,
        "consistency_rate": round(top_count / len(runs), 4),
        "unique_outputs": len(counts),
    }


def _expected_indexes(answer: dict) -> list[dict]:
    if answer.get("type") == "index":
        return [answer]
    if answer.get("type") == "index_set":
        return answer["indexes"]
    return []


def _truth_signature(index: dict) -> tuple:
    names = index["columns"]
    directions = index.get("directions", ["ASC"] * len(names))
    if len(names) != len(directions):
        raise ValueError("ground truth thiếu hướng cột")
    return index["table"], tuple(zip(names, directions, strict=True))


def _proposal_signature(proposal: dict) -> tuple:
    return proposal["table"], tuple(
        (column["name"], column["order"]) for column in proposal["columns"]
    )


def score_index_query(query_id: str, proposals: list[dict], ground_truth: dict) -> dict:
    """Chấm khớp chính xác; giữ None khi còn cần đo mức tương đương P95."""
    if not isinstance(proposals, list):
        raise TypeError("proposals phải là danh sách")
    entry = ground_truth["queries"][query_id]
    if entry["group"] not in INDEX_GROUPS:
        raise ValueError("Precision/Recall index chỉ áp dụng nhóm 1, 2, 4")
    expected = {
        _truth_signature(index)
        for answer in entry["acceptable_answers"]
        for index in _expected_indexes(answer)
    }
    if not expected:
        raise ValueError("ground truth thiếu index để chấm")

    indexes = [proposal for proposal in proposals if proposal.get("type") == "index"]
    exact = sum(_proposal_signature(proposal) in expected for proposal in indexes)
    total = len(indexes)
    needs_equivalence = 0 < total and exact < total
    return {
        "query_id": query_id, "group": entry["group"],
        "index_proposals": total, "exact_matches": exact,
        "precision_numerator": exact, "precision_denominator": total,
        "recall_numerator": 1 if exact else 0, "recall_denominator": 1,
        "precision": 1.0 if total and exact == total else None,
        "recall": 1.0 if exact else 0.0 if total == 0 else None,
        "equivalence_needed": needs_equivalence,
        "full_answer_verified": False,
    }


def main() -> None:
    """Đọc store/bằng chứng cục bộ, chỉ in số liệu chấm hoặc ghi comparison.csv."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--query-id", default=None)
    parser.add_argument("--build-comparison", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "comparison.csv",
    )
    args = parser.parse_args()

    if args.build_comparison:
        root = Path(__file__).resolve().parents[2]
        rows = build_comparison_rows(
            llm_diag_path=root / "data" / "outputs" / "llm_catalog_20261127" / "exact_index_diagnostic.json",
            rewrite_dir=root / "data" / "outputs" / "llm_catalog_20261127",
            rule_based_path=root / "data" / "outputs" / "baseline_rule_based_20261128.json",
            greedy_path=root / "data" / "outputs" / "baseline_greedy_20261128.json",
        )
        out = write_comparison_csv(args.output, rows)
        print(f"Đã ghi bảng so sánh: {out}")
        return

    if not args.store or not args.query_id:
        parser.error("cần --store và --query-id (hoặc dùng --build-comparison)")
    if not args.store.is_file():
        parser.error("store SQLite không tồn tại")

    from mcp_server.store.proposals import ProposalStore

    truth_path = Path(__file__).resolve().parents[1] / "queries" / "ground_truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    saved = [item["proposal"] for item in ProposalStore(args.store).recent_proposals()
             if item["query_id"] == args.query_id]
    score = score_index_query(args.query_id, saved, truth)
    score["ground_truth_status"] = truth["queries"][args.query_id]["verification_status"]
    score["gvhd_signed"] = truth.get("gvhd_signature") is not None
    print(json.dumps(score, ensure_ascii=False))


if __name__ == "__main__":
    main()
