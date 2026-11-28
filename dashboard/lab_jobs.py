"""
dashboard/lab_jobs.py
---------------------

CHỨC NĂNG : Chạy phép đo dài trên validation lab 3309 ở TIẾN TRÌNH RIÊNG
            (scripts/lab_demo_runner.py) để trang không bị đứng 15–20 phút và
            vẫn giữ nguyên guard an toàn (DB 3307 chỉ đọc).
PHỤ TRÁCH  : Tình · Vũ    |    REVIEW: Hải
LƯU Ý      : Mỗi lần chỉ một phép đo trên lab (không chạy benchmark song song).
             Kết quả/tiến độ ghi file trong data/outputs/dashboard_jobs/ (gitignored).
"""

import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

from security.ast_whitelist import check as ast_check

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "data" / "outputs" / "dashboard_jobs"
SOURCES = ("llm", "greedy")
MODES = ("fast", "quick", "full")
_JOB_ID_RE = re.compile(r"^(llm|greedy)_\d{9,12}_[0-9a-f]{4}$")
_HANDLES: dict[str, subprocess.Popen] = {}


def lab_port_open(port: int = 3309, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _job_dir(job_id: str, jobs_dir: Path | None = None) -> Path:
    if not isinstance(job_id, str) or not _JOB_ID_RE.match(job_id):
        raise ValueError("job_id không hợp lệ")
    return (jobs_dir or JOBS_DIR) / job_id


def running_job_ids() -> list[str]:
    return [job_id for job_id, handle in list(_HANDLES.items()) if handle.poll() is None]


def start_job(source: str, *, query_id: str, sql: str, mode: str,
              proposal_ids: list[str] | None = None, store_path: Path | str | None = None,
              jobs_dir: Path | None = None, popen=subprocess.Popen) -> str:
    """Khởi chạy phép đo; source = llm (đề xuất đã lưu) hoặc greedy (baseline)."""
    if source not in SOURCES or mode not in MODES:
        raise ValueError("source hoặc mode không hợp lệ")
    if not isinstance(query_id, str) or not query_id.strip():
        raise ValueError("query_id không hợp lệ")
    if not isinstance(sql, str) or not ast_check(sql)[0]:
        raise ValueError("SQL không qua AST whitelist")
    if running_job_ids():
        raise RuntimeError("Đang có một phép đo khác chạy trên lab, hãy đợi nó xong.")

    job_id = f"{source}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    directory = _job_dir(job_id, jobs_dir)
    directory.mkdir(parents=True, exist_ok=True)
    request = {
        "query_id": query_id, "sql": sql, "source": source, "mode": mode,
        "proposal_ids": list(proposal_ids or []), "started_at": time.time(),
    }
    (directory / "request.json").write_text(
        json.dumps(request, ensure_ascii=False), encoding="utf-8")
    command = [sys.executable, "-m", "scripts.lab_demo_runner", "measure",
               "--request", str(directory / "request.json"),
               "--out", str(directory / "result.json")]
    if store_path is not None:
        command += ["--store", str(store_path)]
    env = {**os.environ, "DB_HOST": "127.0.0.1", "DB_PORT": "3309", "DB_NAME": "shopdb"}
    log = open(directory / "runner.log", "wb")  # noqa: SIM115 - giữ mở cho tiến trình con
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    _HANDLES[job_id] = popen(command, cwd=str(ROOT), env=env, stdout=log,
                             stderr=subprocess.STDOUT, creationflags=flags)
    return job_id


def job_status(job_id: str, *, jobs_dir: Path | None = None) -> dict:
    """state: running | done | failed; kèm tiến độ, thời gian đã chạy và kết quả."""
    directory = _job_dir(job_id, jobs_dir)
    request = {}
    if (directory / "request.json").is_file():
        request = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    elapsed = round(time.time() - request.get("started_at", time.time()), 1)
    progress = ""
    if (directory / "progress.json").is_file():
        try:
            progress = json.loads(
                (directory / "progress.json").read_text(encoding="utf-8")).get("stage", "")
        except (json.JSONDecodeError, OSError):
            progress = ""
    result_path = directory / "result.json"
    if result_path.is_file():
        return {"state": "done", "result": json.loads(result_path.read_text(encoding="utf-8")),
                "progress": progress, "elapsed_s": elapsed, "request": request}
    handle = _HANDLES.get(job_id)
    state = "running" if handle is not None and handle.poll() is None else "failed"
    return {"state": state, "result": None, "progress": progress,
            "elapsed_s": elapsed, "request": request}
