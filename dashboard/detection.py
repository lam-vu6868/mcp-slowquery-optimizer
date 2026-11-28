"""
dashboard/detection.py
----------------------

CHỨC NĂNG : So sánh khâu PHÁT HIỆN query chậm: pt-query-digest (hoặc parser dự phòng)
            đọc slow log vs Tool 1 get_slow_queries của hệ thống.
PHỤ TRÁCH  : Tường · Tình    |    REVIEW: Hải
LƯU Ý      : Chỉ đọc mysql.slow_log bằng readonly_user trên DB hiện tại (3307).
             pt-query-digest không đề xuất index nên không dùng cho Precision/Recall.
"""

import time
from pathlib import Path

from data.baseline.pt_query_digest import (
    compare_top_n,
    fingerprint_id,
    run_pt_query_digest,
)

EXPORT_LIMIT = 2000


def _seconds(value) -> float:
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def slow_log_rows_to_text(rows: list[dict]) -> str:
    """Dựng lại nội dung file slow log chuẩn MySQL từ các dòng mysql.slow_log."""
    parts: list[str] = []
    for row in rows:
        sql = row.get("sql_text")
        if isinstance(sql, (bytes, bytearray)):
            sql = bytes(sql).decode("utf-8", errors="replace")
        if not isinstance(sql, str) or not sql.strip():
            continue
        one_line = " ".join(line.strip() for line in sql.strip().splitlines()
                            if line.strip() and not line.strip().startswith("#"))
        if not one_line:
            continue
        parts.append(
            "# User@Host: readonly_user[readonly_user] @ localhost []\n"
            f"# Query_time: {_seconds(row.get('query_time')):.6f}  "
            f"Lock_time: {_seconds(row.get('lock_time')):.6f} "
            f"Rows_sent: {int(row.get('rows_sent') or 0)}  "
            f"Rows_examined: {int(row.get('rows_examined') or 0)}\n"
            f"{one_line.rstrip(';')};\n"
        )
    return "".join(parts)


def read_slow_log_table(limit: int = EXPORT_LIMIT) -> list[dict]:
    from mcp_server.utils.config import Config
    from mcp_server.utils.db import get_conn
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT query_time, lock_time, rows_sent, rows_examined, "
            "CAST(sql_text AS CHAR) AS sql_text FROM mysql.slow_log "
            "WHERE db = %s AND sql_text IS NOT NULL "
            "  AND (LTRIM(CONVERT(sql_text USING utf8mb4)) LIKE 'SELECT%%' "
            "       OR LTRIM(CONVERT(sql_text USING utf8mb4)) LIKE 'WITH%%') "
            "ORDER BY start_time DESC LIMIT %s",
            (Config.DB_NAME, int(limit)),
        )
        return list(cur.fetchall())


def export_slow_log(path: Path, *, reader=read_slow_log_table) -> int:
    """Ghi file slow log từ bảng mysql.slow_log; trả số bản ghi đã ghi."""
    rows = reader()
    text = slow_log_rows_to_text(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text.count("# Query_time:")


def group_tool1_rows(rows: list[dict], *, top_n: int = 10) -> list[dict]:
    """Gom nhóm các dòng Tool 1 cùng fingerprint (nhất là nhánh slow_log) để so ngang pt-query-digest."""
    grouped: dict[str, dict] = {}
    for row in rows:
        sql = row.get("sql_text") or ""
        fid = fingerprint_id(sql)
        count = int(row.get("exec_count") or 1)
        avg_ms = float(row.get("avg_latency_ms") or 0.0)
        total_ms = float(row.get("total_latency_ms") or (avg_ms * count))
        entry = grouped.get(fid)
        if entry is None:
            grouped[fid] = {
                **row,
                "exec_count": count,
                "total_latency_ms": total_ms,
                "avg_latency_ms": round(total_ms / max(count, 1), 2),
            }
        else:
            entry["exec_count"] += count
            entry["total_latency_ms"] += total_ms
            entry["avg_latency_ms"] = round(
                entry["total_latency_ms"] / max(entry["exec_count"], 1), 2,
            )
    ranked = sorted(grouped.values(), key=lambda item: item["total_latency_ms"], reverse=True)
    return ranked[:top_n]


def detection_comparison(tool1_rows: list[dict], pt_result: dict, *,
                         tool1_ms: float | None, top_n: int = 10) -> dict:
    """Bảng top-N của hai bên cùng độ trùng khớp (overlap, Jaccard) và thời gian phân tích."""
    grouped_rows = group_tool1_rows(tool1_rows, top_n=top_n)
    summary = compare_top_n(pt_result, grouped_rows, tool1_duration_ms=tool1_ms, top_n=top_n)
    tool1_ids = {fingerprint_id(r.get("sql_text") or "") for r in grouped_rows[:top_n]}
    pt_ids = {item["fingerprint_id"] for item in pt_result.get("top_queries", [])[:top_n]}
    tool1_table = [{
        "Hạng": i + 1,
        "SQL": (row.get("sql_text") or "")[:100],
        "Số lần": row.get("exec_count"),
        "TB (ms)": row.get("avg_latency_ms"),
        "Có trong pt-query-digest": fingerprint_id(row.get("sql_text") or "") in pt_ids,
    } for i, row in enumerate(grouped_rows[:top_n])]
    pt_table = [{
        "Hạng": i + 1,
        "SQL mẫu": (item.get("sample_sql") or "")[:100],
        "Số lần": item.get("count"),
        "TB (ms)": item.get("avg_latency_ms"),
        "Có trong Tool 1": item["fingerprint_id"] in tool1_ids,
    } for i, item in enumerate(pt_result.get("top_queries", [])[:top_n])]
    return {"summary": summary, "tool1": tool1_table, "pt": pt_table}


def measure_tool1_ms(loader) -> tuple[list[dict], float]:
    """Gọi hàm tải Tool 1 và đo thời gian phân tích (ms)."""
    t0 = time.perf_counter()
    rows = loader()
    return rows, round((time.perf_counter() - t0) * 1000.0, 2)


def run_pt(path: Path, *, limit: int = 10, binary: str = "pt-query-digest") -> dict:
    return run_pt_query_digest(path, limit=limit, binary=binary)
