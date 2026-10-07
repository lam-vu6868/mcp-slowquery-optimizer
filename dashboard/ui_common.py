"""
dashboard/ui_common.py
----------------------

CHỨC NĂNG :
    Hàm dùng chung cho app.py và 4 tab: nạp CSS, đọc dữ liệu AN TOÀN (không crash
    khi chưa có dữ liệu), kiểm tra kết nối DB, hiển thị SQL không tin cậy.

PHỤ TRÁCH  : Tình    |    REVIEW: Tường

LƯU Ý:
    - Mọi hàm load_* trả None / [] khi chưa có dữ liệu, KHÔNG raise
      (tuần 1 từng crash khi bảng trống).
    - Dashboard KHÔNG tự chạy DDL. Kết nối DB ở đây chỉ dùng readonly_user.
    - SQL lấy từ DB/LLM là dữ liệu không tin cậy: chỉ hiển thị bằng st.code,
      không bao giờ render HTML/Markdown từ nó.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parent
ROOT = DASHBOARD_DIR.parent
if str(ROOT) not in sys.path:  # để import được security/, mcp_server/
    sys.path.insert(0, str(ROOT))

SECURITY_LOG_DIR = ROOT / "security" / "logs"
COMPARISON_CSV = ROOT / "data" / "metrics" / "comparison.csv"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # python-dotenv là tùy chọn
    pass


# ---------------------------------------------------------------------------
# Giao diện
# ---------------------------------------------------------------------------


def setup_page(title: str, icon: str = "🛢️") -> None:
    st.set_page_config(page_title=f"{title} · Slow Query Optimizer", page_icon=icon, layout="wide")
    css = DASHBOARD_DIR / "assets" / "style.css"
    try:
        st.markdown(f"<style>{css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    except OSError:
        pass


def empty_state(message: str, hint: Optional[str] = None) -> None:
    st.info(message, icon="ℹ️")
    if hint:
        st.caption(hint)


def show_untrusted_sql(sql: Optional[str], *, label: str = "SQL (dữ liệu không tin cậy)") -> None:
    """Hiển thị SQL từ slow log / LLM dạng text thuần."""

    st.caption(label)
    st.code(sql or "", language="sql")


def status_badge(status: str) -> str:
    """Trả HTML badge cho trạng thái (giá trị status do server đặt, không phải từ LLM)."""

    allowed = {"pending", "passed", "failed", "approved", "rejected", "applied"}
    key = status if status in allowed else "pending"
    return f'<span class="badge badge-{key}">{key}</span>'


# ---------------------------------------------------------------------------
# Kết nối DB (chỉ readonly)
# ---------------------------------------------------------------------------


def db_status() -> Dict[str, Any]:
    """Thử kết nối readonly_user theo .env hiện tại. Không raise."""

    return _probe_db(
        os.getenv("DB_HOST", "127.0.0.1"),
        int(os.getenv("DB_PORT", "3307")),
        os.getenv("DB_USER", "readonly_user"),
        os.getenv("DB_PASSWORD", "readonly_pass"),
        os.getenv("DB_NAME", "shopdb"),
    )


@st.cache_data(ttl=30, show_spinner=False)
def _probe_db(host: str, port: int, user: str, password: str, database: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {"ok": False, "host": host, "port": port, "error": None, "version": None}
    try:
        import pymysql

        conn = pymysql.connect(
            host=host, port=port, user=user, password=password, database=database, connect_timeout=2
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION()")
                info["version"] = cur.fetchone()[0]
        finally:
            conn.close()
        info["ok"] = True
    except Exception as exc:  # thiếu thư viện, sai mật khẩu, DB chưa chạy...
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


# ---------------------------------------------------------------------------
# Nguồn dữ liệu — mỗi hàm trả None/[] khi chưa có
# ---------------------------------------------------------------------------


def load_slow_queries(limit: int = 10) -> Optional[List[Dict[str, Any]]]:
    """Tool 1 (Vũ). Trả None khi tool chưa cài đặt hoặc lỗi."""

    try:
        from mcp_server.tools import slow_queries

        fn = getattr(slow_queries, "get_slow_queries", None)
        if fn is None:
            return None
        result = fn(limit=limit)
        if isinstance(result, dict):  # định dạng {ok, data, error, meta}
            if not result.get("ok"):
                return None
            return list((result.get("data") or {}).get("queries") or [])
        return list(result or [])
    except Exception:
        return None


def load_proposals() -> Optional[List[Dict[str, Any]]]:
    """Store proposals (Hải). Trả None khi chưa cài đặt."""

    try:
        from mcp_server.store import proposals

        fn = getattr(proposals, "list_proposals", None)
        return list(fn()) if fn else None
    except Exception:
        return None


def load_comparison():
    """data/metrics/comparison.csv (Tường). Trả DataFrame hoặc None."""

    try:
        import pandas as pd

        if not COMPARISON_CSV.exists():
            return None
        df = pd.read_csv(COMPARISON_CSV)
        return df if not df.empty else None
    except Exception:
        return None


def load_latest_injection_log() -> Optional[Dict[str, Any]]:
    """Kết quả mới nhất của security/injection_tests (Tình)."""

    try:
        logs = sorted(SECURITY_LOG_DIR.glob("injection_tests_*.json"))
        if not logs:
            return None
        data = json.loads(logs[-1].read_text(encoding="utf-8"))
        data["_file"] = logs[-1].name
        return data
    except Exception:
        return None


def load_audit_log() -> Optional[List[Dict[str, Any]]]:
    """Audit log Tool 6 (Hải/Tình). Trả None khi chưa cài đặt."""

    try:
        from mcp_server.store import audit_log

        fn = getattr(audit_log, "list_entries", None)
        return list(fn()) if fn else None
    except Exception:
        return None
