"""
data/baseline/pt_query_digest.py
--------------------------------

CHỨC NĂNG :
    Chạy pt-query-digest trên slow log file để so sánh khâu PHÁT HIỆN/xếp hạng query chậm.

PHỤ TRÁCH  : Tường    |    REVIEW: Hải

LƯU Ý:
    - pt-query-digest KHÔNG đề xuất index: không đưa vào bảng Precision/Recall.
    - Cần log_output có FILE để có file slow log.

THAM KHẢO  : project-management/ROADMAP.md (mục 2.5)

TRẠNG THÁI : ĐÃ CÀI ĐẶT — gọi pt-query-digest (có fallback parser slow log thuần Python) và so sánh Top-N với Tool 1.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

_STAT_RE = re.compile(
    r"#\s*Query_time:\s*([0-9.]+)\s+Lock_time:\s*([0-9.]+)\s+"
    r"Rows_sent:\s*(\d+)\s+Rows_examined:\s*(\d+)"
)
_STRING_LIT_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
_NUMBER_LIT_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_WS_RE = re.compile(r"\s+")
_SPACE_AROUND_OPS_RE = re.compile(r"\s*([(),=<>+\-*/])\s*")


def fingerprint_sql(sql: str) -> str:
    """Chuẩn hóa SQL thành fingerprint (thay hằng số bằng ?) để gom nhóm."""
    cleaned = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    cleaned = cleaned.replace("`", "")
    cleaned = _STRING_LIT_RE.sub("?", cleaned)
    cleaned = _NUMBER_LIT_RE.sub("?", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip().rstrip(";").lower()
    return _SPACE_AROUND_OPS_RE.sub(r"\1", cleaned)


def fingerprint_id(sql: str) -> str:
    fp = fingerprint_sql(sql)
    return hashlib.sha256(fp.encode("utf-8")).hexdigest()[:16]


def parse_slow_log_file(log_path: str | Path, *, limit: int = 10) -> dict:
    """Đọc file slow query log chuẩn MySQL và xếp hạng Top N theo tổng Query_time."""
    t0 = time.perf_counter()
    path = Path(log_path)
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file slow log: {path}")

    buckets: dict[str, dict] = {}
    current_stats: tuple[float, float, int, int] | None = None
    sql_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_stats, sql_lines
        if current_stats is None or not sql_lines:
            current_stats = None
            sql_lines = []
            return
        raw_sql = " ".join(
            line for line in sql_lines
            if not line.upper().startswith(("SET TIMESTAMP=", "USE "))
        ).strip()
        if raw_sql:
            fp = fingerprint_sql(raw_sql)
            fp_id = hashlib.sha256(fp.encode("utf-8")).hexdigest()[:16]
            q_time_s, _lock_s, _rows_sent, rows_examined = current_stats
            q_time_ms = q_time_s * 1000.0
            entry = buckets.setdefault(
                fp_id,
                {
                    "fingerprint_id": fp_id,
                    "count": 0,
                    "total_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                    "total_rows_examined": 0,
                    "sample_sql": raw_sql[:200],
                },
            )
            entry["count"] += 1
            entry["total_latency_ms"] += q_time_ms
            entry["max_latency_ms"] = max(entry["max_latency_ms"], q_time_ms)
            entry["total_rows_examined"] += rows_examined
        current_stats = None
        sql_lines = []

    with path.open(encoding="utf-8", errors="replace") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            match = _STAT_RE.match(line)
            if match:
                _flush()
                current_stats = (
                    float(match.group(1)),
                    float(match.group(2)),
                    int(match.group(3)),
                    int(match.group(4)),
                )
            elif line.startswith("#"):
                continue
            elif current_stats is not None:
                sql_lines.append(line)
        _flush()

    ranked = sorted(buckets.values(), key=lambda x: x["total_latency_ms"], reverse=True)
    top_items = []
    for item in ranked[:limit]:
        count = item["count"]
        top_items.append({
            "fingerprint_id": item["fingerprint_id"],
            "count": count,
            "total_latency_ms": round(item["total_latency_ms"], 2),
            "avg_latency_ms": round(item["total_latency_ms"] / count, 2),
            "max_latency_ms": round(item["max_latency_ms"], 2),
            "avg_rows_examined": round(item["total_rows_examined"] / count, 1),
            "sample_sql": item.get("sample_sql", ""),
        })

    duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "engine": "python_slow_log_fallback",
        "log_path": str(path),
        "total_unique_queries": len(buckets),
        "duration_ms": duration_ms,
        "top_queries": top_items,
    }


def run_pt_query_digest(
    log_path: str | Path, *, limit: int = 10, binary: str = "pt-query-digest"
) -> dict:
    """Chạy pt-query-digest nếu có trên hệ thống; nếu không thì fallback parser Python."""
    path = Path(log_path)
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file slow log: {path}")

    resolved = shutil.which(binary)
    if not resolved:
        return parse_slow_log_file(path, limit=limit)

    t0 = time.perf_counter()
    proc = subprocess.run(
        [resolved, "--output", "json", f"--limit={limit}", str(path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    if proc.returncode != 0:
        fallback = parse_slow_log_file(path, limit=limit)
        fallback["pt_error"] = f"returncode={proc.returncode}"
        return fallback

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return parse_slow_log_file(path, limit=limit)

    classes = payload.get("classes") or []
    top_items = []
    for cls in classes[:limit]:
        fp = cls.get("fingerprint", "")
        metrics = cls.get("metrics", {})
        qt = metrics.get("Query_time", {})
        re_m = metrics.get("Rows_examined", {})
        top_items.append({
            "fingerprint_id": fingerprint_id(fp),
            "count": int(cls.get("query_count", 0)),
            "total_latency_ms": round(float(qt.get("sum", 0.0)) * 1000.0, 2),
            "avg_latency_ms": round(float(qt.get("avg", 0.0)) * 1000.0, 2),
            "max_latency_ms": round(float(qt.get("max", 0.0)) * 1000.0, 2),
            "avg_rows_examined": round(float(re_m.get("avg", 0.0)), 1),
            "sample_sql": fp[:200],
        })
    return {
        "engine": "pt-query-digest",
        "log_path": str(path),
        "total_unique_queries": len(classes),
        "duration_ms": duration_ms,
        "top_queries": top_items,
    }


def compare_top_n(
    pt_result: dict,
    tool1_queries: list[dict],
    *,
    tool1_duration_ms: float | None = None,
    top_n: int = 10,
) -> dict:
    """So sánh Top-N query chậm giữa pt-query-digest và Tool 1 (get_slow_queries)."""
    pt_ids = [item["fingerprint_id"] for item in pt_result.get("top_queries", [])[:top_n]]
    tool1_ids = [
        fingerprint_id(q.get("sql_text") or q.get("digest_text") or "")
        for q in tool1_queries[:top_n]
        if (q.get("sql_text") or q.get("digest_text"))
    ]
    pt_set = set(pt_ids)
    t1_set = set(tool1_ids)
    overlap = pt_set & t1_set
    union = pt_set | t1_set
    return {
        "top_n": top_n,
        "pt_engine": pt_result.get("engine"),
        "pt_count": len(pt_set),
        "tool1_count": len(t1_set),
        "overlap_count": len(overlap),
        "jaccard_similarity": round(len(overlap) / len(union), 4) if union else 0.0,
        "pt_duration_ms": pt_result.get("duration_ms"),
        "tool1_duration_ms": tool1_duration_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phân tích file slow log bằng pt-query-digest (hoặc fallback parser)."
    )
    parser.add_argument("log_path", type=Path, help="Đường dẫn file MySQL slow query log")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", "-o", type=Path, default=None)
    args = parser.parse_args()

    result = run_pt_query_digest(args.log_path, limit=args.limit)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Đã lưu kết quả pt-query-digest: {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
