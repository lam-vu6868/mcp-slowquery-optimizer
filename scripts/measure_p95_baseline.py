"""Do P95 baseline cho 30 query va luu ket qua sau tung query."""
import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.queries.queries import QUERIES
from mcp_server.tools.benchmark import benchmark_query


DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "outputs" / "p95_baseline_raw.json"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def git_value(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def load_output(path: Path) -> dict:
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        payload.setdefault("results", {})
        return payload

    return {
        "meta": {
            "dataset": "shopdb.sales_data",
            "method": "streaming end-to-end latency; separate result hash pass",
            "warmup_runs": 3,
            "measured_runs": 20,
            "timeout_ms": 60000,
            "cache_state": "warm",
            "started_at": now_iso(),
            "source_branch": git_value("branch", "--show-current"),
            "source_commit": git_value("rev-parse", "HEAD"),
        },
        "results": {},
    }


def save_output(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temporary, path)


def select_queries(group: int | None, ids: list[str] | None) -> list[dict]:
    selected = QUERIES
    if group is not None:
        selected = [query for query in selected if query["group"] == group]
    if ids:
        requested = {query_id.lower() for query_id in ids}
        selected = [query for query in selected if query["id"].lower() in requested]
        found = {query["id"].lower() for query in selected}
        missing = sorted(requested - found)
        if missing:
            raise ValueError("Khong tim thay query: " + ", ".join(missing))
    return selected


async def run(args) -> int:
    output_path = Path(args.output).resolve()
    payload = load_output(output_path)
    selected = select_queries(args.group, args.ids)

    print("=" * 80)
    print("DO P95 BASELINE - WARM-UP 3, MEASURED 20, TIMEOUT 60000 MS")
    print(f"Output: {output_path}")
    print(f"So query duoc chon: {len(selected)}")
    print("=" * 80)

    valid_count = 0
    failed_count = 0

    for position, query in enumerate(selected, start=1):
        query_id = query["id"]
        existing = payload["results"].get(query_id)
        if existing and existing.get("status") == "valid" and not args.force:
            valid_count += 1
            print(f"[{position}/{len(selected)}] {query_id}: bo qua (da valid)")
            continue

        print(f"\n[{position}/{len(selected)}] Dang do {query_id} - nhom {query['group']}")
        measured_at = now_iso()

        try:
            raw_response = await benchmark_query(
                query["sql"],
                warmup_runs=3,
                measured_runs=20,
                timeout_ms=60000,
                use_invisible_indexes=False,
                compute_result_hash=True,
            )
            response = json.loads(raw_response)

            if response.get("ok"):
                data = response["data"]
                is_valid = (
                    data.get("runs") == 20
                    and data.get("timed_out_runs") == 0
                    and data.get("result_hash")
                )
                entry = {
                    "id": query_id,
                    "group": query["group"],
                    "description": query["description"],
                    "sql": query["sql"],
                    "status": "valid" if is_valid else "invalid",
                    "measured_by": "Hai",
                    "measured_at": measured_at,
                    **data,
                }
            else:
                entry = {
                    "id": query_id,
                    "group": query["group"],
                    "description": query["description"],
                    "sql": query["sql"],
                    "status": "error",
                    "measured_by": "Hai",
                    "measured_at": measured_at,
                    "error": response.get("error"),
                }

        except KeyboardInterrupt:
            payload["meta"]["last_interrupted_at"] = now_iso()
            save_output(output_path, payload)
            print("\nDa luu ket qua truoc khi dung.")
            raise
        except Exception as exc:
            entry = {
                "id": query_id,
                "group": query["group"],
                "description": query["description"],
                "sql": query["sql"],
                "status": "error",
                "measured_by": "Hai",
                "measured_at": measured_at,
                "error": {"code": "SCRIPT_ERROR", "message": str(exc)[:500]},
            }

        payload["results"][query_id] = entry
        payload["meta"]["last_updated_at"] = now_iso()
        save_output(output_path, payload)

        if entry["status"] == "valid":
            valid_count += 1
            print(
                f"{query_id}: VALID | p50={entry['p50_ms']} ms | "
                f"p95={entry['p95_ms']} ms | rows={entry['row_count']} | "
                f"examined={entry['rows_examined']}"
            )
        else:
            failed_count += 1
            print(f"{query_id}: {entry['status'].upper()} | {entry.get('error')}")

    all_results = payload["results"]
    payload["meta"]["completed_valid_count"] = sum(
        result.get("status") == "valid" for result in all_results.values()
    )
    payload["meta"]["completed_total_count"] = len(all_results)
    payload["meta"]["last_completed_at"] = now_iso()
    save_output(output_path, payload)

    print("\n" + "=" * 80)
    print(f"Valid trong lan chay nay: {valid_count}")
    print(f"Loi/khong hop le: {failed_count}")
    print(f"Da luu: {output_path}")
    print("=" * 80)
    return 0 if failed_count == 0 else 1


def parse_args():
    parser = argparse.ArgumentParser(description="Do P95 baseline cho 30 query")
    parser.add_argument("--group", type=int, choices=range(1, 6))
    parser.add_argument("--ids", nargs="+", help="Vi du: --ids q01 q07")
    parser.add_argument("--force", action="store_true", help="Do lai query da valid")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    if args.group is not None and args.ids:
        parser.error("Chi dung mot trong hai: --group hoac --ids")
    return args


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
