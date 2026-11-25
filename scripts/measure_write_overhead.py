"""Đo INSERT trên MySQL write lab riêng và lưu bằng chứng JSON, không chạy trên DB chính."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from mcp_server.validation.write_overhead import measure_insert_overhead


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure INSERT overhead on isolated MySQL lab")
    parser.add_argument("--table", required=True)
    parser.add_argument("--index-name", required=True)
    parser.add_argument("--columns", nargs="+", required=True,
                        help="Example: status:ASC order_date:ASC")
    parser.add_argument("--csv-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    columns = []
    for part in args.columns:
        name, separator, order = part.partition(":")
        if not separator:
            parser.error("each column must be name:ASC or name:DESC")
        columns.append({"name": name, "order": order})
    proposal = {
        "type": "index", "table": args.table,
        "index_name": args.index_name, "columns": columns,
    }
    if args.output.exists():
        parser.error("output file already exists")
    data = measure_insert_overhead(proposal, csv_dir=args.csv_dir)
    evidence = {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "table": args.table, "index_name": args.index_name,
        "columns": columns, "data": data,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(evidence, file, ensure_ascii=False, indent=2)
    print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
