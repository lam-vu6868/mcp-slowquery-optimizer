"""
dashboard/common.py
-------------------
CHỨC NĂNG:
    Hàm dùng chung cho Dashboard: cấu hình trang, CSS, đọc dữ liệu từ các nguồn
    (Tool 1, store proposals/validation, audit log, kết quả injection, comparison.csv).

PHỤ TRÁCH: Tình    |    REVIEW: Tường

LƯU Ý:
    - Mọi hàm đọc dữ liệu đều trả (data, ghi_chú_lỗi) và KHÔNG ném lỗi ra ngoài:
      Dashboard phải chạy được kể cả khi chưa có dữ liệu / chưa có MySQL (trước đây từng crash).
    - Dashboard KHÔNG tự chạy DDL. Chỉ trang 2 gọi Tool 6 kèm approval token.
"""
import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

INJECTION_RESULTS = ROOT / "security" / "logs" / "injection_results.json"
COMPARISON_CSV = ROOT / "data" / "metrics" / "comparison.csv"
QUERIES_FILE = ROOT / "data" / "queries" / "queries.py"
GROUND_TRUTH = ROOT / "data" / "queries" / "ground_truth.json"

STATUS_LABELS = {
    "pending_validation": ("Chờ validation", "pending"),
    "validated": ("Đã pass validation — chờ duyệt", "ready"),
    "rejected_by_validation": ("Validation từ chối", "rejected"),
    "rejected_by_user": ("Người duyệt từ chối", "rejected"),
    "applied": ("Đã áp dụng", "approved"),
    "apply_failed": ("Áp dụng lỗi", "rejected"),
}

GROUP_NAMES = {
    1: "Thiếu index", 2: "Sai thứ tự cột composite", 3: "Hàm bọc cột (non-sargable)",
    4: "SELECT * + filesort", 5: "Subquery → JOIN",
}


# ============================================================
# TRANG
# ============================================================

def setup_page(title: str, icon: str = "🛢️"):
    st.set_page_config(page_title=f"{title} · Slow Query Optimizer", page_icon=icon, layout="wide")
    css = ROOT / "dashboard" / "assets" / "style.css"
    try:
        st.markdown(f"<style>{css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    except OSError:
        pass
    if is_demo_meta():
        st.warning("Đang dùng **dữ liệu demo** (META_DB_PATH trỏ tới file demo). "
                   "Số liệu trên trang KHÔNG phải kết quả thực nghiệm.", icon="🧪")


def badge(status: str) -> str:
    label, css = STATUS_LABELS.get(status, (status, "pending"))
    return f'<span class="badge badge-{css}">{label}</span>'


def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:  # đã có event loop (hiếm với Streamlit)
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def is_demo_meta() -> bool:
    return "demo" in (os.getenv("META_DB_PATH") or "").lower()


# ============================================================
# NGUỒN DỮ LIỆU
# ============================================================

def load_slow_queries(limit: int = 50):
    """Tool 1 get_slow_queries. Trả (list | None, ghi chú)."""
    try:
        from mcp_server.tools.slow_queries import get_slow_queries  # Vũ
    except ImportError:
        return None, "Tool 1 `get_slow_queries` chưa sẵn sàng (mcp_server/tools/slow_queries.py)."
    try:
        res = run_async(get_slow_queries(limit=limit))
        res = json.loads(res) if isinstance(res, str) else res
        if not res.get("ok"):
            return None, f"Tool 1 lỗi: {res.get('error', {}).get('message')}"
        return res["data"]["queries"], None
    except Exception as e:
        return None, f"Không gọi được Tool 1: {str(e)[:150]}"


@st.cache_data(ttl=300)
def load_query_catalog() -> pd.DataFrame:
    """30 query thực nghiệm (Tường) + số đo trong ground_truth nếu có."""
    try:
        spec = importlib.util.spec_from_file_location("queries_catalog", QUERIES_FILE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        df = pd.DataFrame(mod.get_all_queries())
    except Exception:
        return pd.DataFrame()
    try:
        gt = json.loads(GROUND_TRUTH.read_text(encoding="utf-8")).get("queries", {})
        df["before_p95_ms"] = df["id"].map(
            lambda q: (gt.get(q, {}).get("measurement") or {}).get("before_p95_ms"))
    except Exception:
        df["before_p95_ms"] = None
    df["group_name"] = df["group"].map(GROUP_NAMES)
    return df


def load_proposals(status=None):
    try:
        from mcp_server.store import proposals as store
        return store.list_proposals(status=status, limit=500), None
    except Exception as e:
        return [], f"Không đọc được store proposals: {str(e)[:150]}"


def load_validation_reports() -> pd.DataFrame:
    """Gộp proposal + validation_report thành bảng phẳng cho tab 3."""
    try:
        from mcp_server.store import proposals as store
        rows = []
        for p in store.list_proposals(limit=500):
            rep = store.get_validation_report(p["proposal_id"])
            if not rep:
                continue
            b, a = rep.get("before") or {}, rep.get("after") or {}
            w = rep.get("write_overhead") or {}
            payload = p["payload"]
            rows.append({
                "query_id": p.get("query_id"),
                "proposal_id": p["proposal_id"],
                "type": p["type"],
                "proposal": (f"{payload.get('table')}({', '.join(c if isinstance(c, str) else c.get('name') for c in payload.get('columns', []))})"
                             if p["type"] == "index" else "rewrite"),
                "status": p["status"],
                "validation": rep.get("status"),
                "result_equivalent": rep.get("result_equivalent"),
                "p95_before_ms": b.get("p95_ms"), "p95_after_ms": a.get("p95_ms"),
                "cost_before": b.get("query_cost"), "cost_after": a.get("query_cost"),
                "rows_before": b.get("rows_examined"), "rows_after": a.get("rows_examined"),
                "improvement_ratio": rep.get("improvement_ratio"),
                "index_size_bytes": w.get("index_size_bytes"),
                "insert_throughput_change_pct": w.get("insert_throughput_change_pct"),
                "failure_reason": rep.get("failure_reason"),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def load_comparison_csv():
    if not COMPARISON_CSV.exists():
        return None, f"Chưa có `{COMPARISON_CSV.relative_to(ROOT)}` (Tường sinh từ data/metrics/metrics.py)."
    try:
        return pd.read_csv(COMPARISON_CSV), None
    except Exception as e:
        return None, f"Không đọc được comparison.csv: {str(e)[:150]}"


def load_injection_results():
    if not INJECTION_RESULTS.exists():
        return None, "Chưa có kết quả. Chạy: `python -m security.injection_tests.run_tests`"
    try:
        return json.loads(INJECTION_RESULTS.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"File kết quả hỏng: {str(e)[:150]}"


def load_audit(limit: int = 500) -> pd.DataFrame:
    try:
        from mcp_server.store import audit_log
        return pd.DataFrame(audit_log.list_entries(limit=limit))
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=30)
def system_status() -> dict:
    out = {}
    try:
        from security import approval
        out["approval_secret"] = approval.is_configured()
    except Exception:
        out["approval_secret"] = False
    try:
        import pymysql
        from mcp_server.utils.config import Config
        conn = pymysql.connect(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
                               password=Config.DB_PASSWORD, database=Config.DB_NAME,
                               connect_timeout=2)
        conn.close()
        out["mysql"] = True
    except Exception:
        out["mysql"] = False
    try:
        from mcp_server.store.meta_db import meta_db_path
        out["meta_db"] = str(meta_db_path())
    except Exception:
        out["meta_db"] = "?"
    return out


def fmt_bytes(n) -> str:
    if n is None or pd.isna(n):
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
