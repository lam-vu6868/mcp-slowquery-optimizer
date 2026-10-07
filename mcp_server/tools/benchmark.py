"""Tool 5: benchmark_query — Tường phụ trách."""

import time
import hashlib
import statistics
from mcp_server.utils.db import get_conn


def benchmark_query(sql, warmup_runs=3, measured_runs=20, timeout_ms=30000, **kwargs):
    start = time.perf_counter()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {timeout_ms}")

                for _ in range(warmup_runs):
                    cur.execute(sql)
                    cur.fetchall()

                lat = []
                for _ in range(measured_runs):
                    t = time.perf_counter()
                    cur.execute(sql)
                    cur.fetchall()
                    lat.append((time.perf_counter() - t) * 1000)

                lat.sort()
                p50 = statistics.median(lat)
                p95 = lat[int(len(lat) * 0.95)] if len(lat) > 1 else lat[0]

                cur.execute(sql)
                rows = cur.fetchall()

                h = hashlib.sha256()
                for r in sorted(rows, key=str):
                    h.update(str(r).encode())

        return {
            "ok": True,
            "data": {
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "min_ms": round(min(lat), 2),
                "max_ms": round(max(lat), 2),
                "runs": len(lat),
                "result_hash": f"sha256:{h.hexdigest()}",
                "row_count": len(rows),
                "deterministic_order": "ORDER BY" in sql.upper(),
                "cache_state": "warm",
                "timed_out_runs": 0,
                "rows_examined": None,
            },
            "error": None,
            "meta": {
                "tool": "benchmark_query",
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "truncated": False,
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "data": None,
            "error": {"code": "INTERNAL", "message": str(e), "detail": {}},
            "meta": {
                "tool": "benchmark_query",
                "duration_ms": int((time.perf_counter() - start) * 1000),
                "truncated": False,
            },
        }