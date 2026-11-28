"""
dashboard/journey.py
--------------------

CHỨC NĂNG : "Hành trình của 1 query" — lưu trong st.session_state những gì người dùng
            vừa CHẠY THẬT ở từng trang (query gốc, đề xuất LLM, phép đo trên lab,
            baseline) để trang sau chỉ hiển thị dữ liệu của chính query đó.
PHỤ TRÁCH  : Tình    |    REVIEW: Vũ
LƯU Ý      : Hàm thuần Python (nhận mapping `state`) để test không cần Streamlit.
             Chưa chạy bước nào thì trang sau phải báo "chưa có dữ liệu", không giả số.
"""

JOURNEY_KEY = "journey"


def get_journey(state) -> dict | None:
    return state.get(JOURNEY_KEY)


def select_query(state, query_id: str, sql: str, source: str) -> dict:
    """Chọn query làm việc. Chọn lại đúng query cũ thì giữ nguyên kết quả đã chạy."""
    if not isinstance(query_id, str) or not query_id.strip():
        raise ValueError("query_id không hợp lệ")
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL rỗng")
    current = state.get(JOURNEY_KEY)
    if current and current["query_id"] == query_id and current["sql"] == sql:
        return current
    state[JOURNEY_KEY] = {
        "query_id": query_id, "sql": sql, "source": source,
        "original_run": None, "explain": None,
        "proposal_ids": [], "jobs": {},
    }
    # Khóa cũ của form LLM (trang 2 đọc và xóa sau khi điền sẵn).
    state["analysis_query_id"] = query_id
    state["analysis_sql"] = sql
    return state[JOURNEY_KEY]


def record_original_run(state, result: dict) -> None:
    journey = _require(state)
    journey["original_run"] = {key: result[key] for key in (
        "latency_ms", "row_count", "rows_examined", "exceeded_slow_threshold",
    )}


def record_explain(state, data: dict) -> None:
    journey = _require(state)
    try:
        cost = float(data.get("query_cost"))
    except (TypeError, ValueError):
        cost = None
    journey["explain"] = {"query_cost": cost}


def record_proposals(state, proposal_ids: list[str]) -> None:
    journey = _require(state)
    journey["proposal_ids"] = list(proposal_ids)
    journey["jobs"] = {}  # đề xuất mới thì các phép đo cũ không còn đúng


def record_job(state, source: str, job_id: str) -> None:
    _require(state)["jobs"][source] = job_id


def job_id_for(state, source: str) -> str | None:
    journey = state.get(JOURNEY_KEY)
    return journey["jobs"].get(source) if journey else None


def build_live_comparison(journey: dict, results: dict) -> list[dict]:
    """Bảng so sánh của query vừa chạy; ô chưa chạy ghi 'chưa chạy' thay vì số giả."""
    original = journey.get("original_run")
    rows = [{
        "Phương pháp": "Query gốc (1 lượt ở bước 1)",
        "Phương án": "—",
        "P95 trước (ms)": original["latency_ms"] if original else "chưa chạy",
        "P95 sau (ms)": "—", "Mức giảm": "—", "Kết quả đúng": "—", "Trạng thái": "—",
    }]
    labels = {"llm": "LLM (Groq + MCP)", "greedy": "Baseline Greedy"}
    for key in ("llm", "greedy"):
        result = results.get(key)
        if result is None:
            rows.append({
                "Phương pháp": labels[key], "Phương án": "chưa chạy",
                "P95 trước (ms)": "chưa chạy", "P95 sau (ms)": "chưa chạy",
                "Mức giảm": "chưa chạy", "Kết quả đúng": "chưa chạy",
                "Trạng thái": "chưa chạy",
            })
            continue
        before, after = result.get("before") or {}, result.get("after") or {}
        gain = improvement_pct(before.get("p95_ms"), after.get("p95_ms"))
        same = (before.get("result_hash") is not None
                and before.get("result_hash") == after.get("result_hash"))
        parts = [f"index {i['table']}({', '.join(i['columns'])})"
                 for i in result.get("indexes", [])]
        if result.get("rewrite_changed"):
            parts.append("viết lại SQL")
        mode = "chính thức" if result.get("official") else "đo nhanh"
        rows.append({
            "Phương pháp": labels[key],
            "Phương án": " + ".join(parts) if parts else "không có đề xuất",
            "P95 trước (ms)": before.get("p95_ms", "—"),
            "P95 sau (ms)": after.get("p95_ms", "—"),
            "Mức giảm": f"{gain:+.2f}%" if gain is not None else "—",
            "Kết quả đúng": "có" if same else "—",
            "Trạng thái": f"{result.get('status')} ({mode})",
        })
    return rows


def improvement_pct(before_ms, after_ms) -> float | None:
    """Phần trăm giảm thời gian; None nếu thiếu số liệu hợp lệ."""
    if type(before_ms) not in (int, float) or type(after_ms) not in (int, float):
        return None
    if before_ms <= 0:
        return None
    return round((before_ms - after_ms) / before_ms * 100.0, 2)


def _require(state) -> dict:
    journey = state.get(JOURNEY_KEY)
    if not journey:
        raise ValueError("chưa chọn query")
    return journey
