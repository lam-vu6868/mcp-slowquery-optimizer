"""Thu proposal LLM từ catalog theo batch nhỏ; Vũ phụ trách, Hải review.

Chỉ gọi backend Dashboard (AST + Groq + MCP Tool 1–5); kết quả ở data/outputs/.
Không chạy Validation/Approve hay DDL. Chạy: python -m scripts.collect_llm_proposals q02 q08
"""

import argparse
import asyncio
import json
from pathlib import Path

from dashboard.backend import generate_proposals_from_dashboard
from data.queries.queries import QUERIES
from mcp_server.store.proposals import ProposalStore

DEFAULT_OUTPUT_DIR = Path("data/outputs/llm_catalog_20261127")
CATALOG = {item["id"]: item for item in QUERIES}


async def collect_many(query_ids: list[str], output_dir: Path) -> list[dict]:
    """Lưu từng query riêng; query đã có proposal được bỏ qua khi chạy lại."""
    if not 1 <= len(query_ids) <= 5 or len(set(query_ids)) != len(query_ids):
        raise ValueError("mỗi batch cần 1–5 query_id khác nhau")
    if any(query_id not in CATALOG for query_id in query_ids):
        raise ValueError("query_id không có trong catalog")

    results = []
    for query_id in query_ids:
        store = ProposalStore(output_dir / f"{query_id}.sqlite3")
        saved = [item for item in store.recent_proposals()
                 if item["query_id"] == query_id]
        if saved:
            results.append({"query_id": query_id, "status": "skipped",
                            "proposal_count": len(saved)})
            continue
        try:
            ids = await generate_proposals_from_dashboard(
                store, query_id, CATALOG[query_id]["sql"],
            )
        except (ExceptionGroup, RuntimeError, ValueError, OSError) as error:
            # Không ghi message ngoại lệ: API/tool có thể chứa SQL hoặc dữ liệu nhạy cảm.
            results.append({"query_id": query_id, "status": "error",
                            "error_type": type(error).__name__})
        else:
            results.append({"query_id": query_id,
                            "status": "ok" if ids else "empty",
                            "proposal_count": len(ids)})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Thu tối đa 5 query catalog mỗi batch")
    parser.add_argument("query_ids", nargs="+", help="Ví dụ: q02 q08 q19")
    args = parser.parse_args()
    try:
        results = asyncio.run(collect_many(args.query_ids, DEFAULT_OUTPUT_DIR))
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(results, ensure_ascii=True))
    if any(item["status"] == "error" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
