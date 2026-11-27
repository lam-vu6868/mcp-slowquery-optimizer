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

TRẠNG THÁI : ĐANG LÀM — chấm khớp index chính xác; chưa chấm tương đương/đủ 30 query.
"""

import argparse
import json
from pathlib import Path

INDEX_GROUPS = {1, 2, 4}


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
    """Đọc store và ground truth cục bộ, chỉ in số liệu chấm (không in SQL)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--query-id", required=True)
    args = parser.parse_args()
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
