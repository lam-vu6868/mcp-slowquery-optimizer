"""
Kiểm chứng ứng viên ground truth trên MySQL lab, lưu bằng chứng sau mỗi query.
PHỤ TRÁCH: Tường | REVIEW: Hải.
LƯU Ý:
    - Chỉ chạy offline khi người dùng cho phép tạo/drop index thử; không đăng ký MCP.
    - SELECT/EXPLAIN dùng get_conn/readonly_user; index_admin chỉ thực thi DDL cố định.
    - Không nhận SQL hoặc tên index từ CLI. Index thử luôn INVISIBLE và được dọn.
    - --check chỉ kiểm tra bằng chứng đã lưu, không kết nối DB.
THAM KHẢO: ROADMAP mục 2.3, benchmark_query, ground_truth_candidates.py.
"""
import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pymysql
import sqlglot
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.queries.ground_truth_candidates import CANDIDATES
from data.queries.queries import QUERIES, get_query_by_id
from mcp_server.tools.benchmark import benchmark_query
from mcp_server.utils.config import Config
from mcp_server.utils.db import get_conn
from scripts.measure_p95_baseline import now_iso, save_output
from security.ast_whitelist import check

FOLDER = ROOT / "data/outputs/ground_truth_validation"
TRUTH = ROOT / "data/queries/ground_truth.json"
BASELINE = ROOT / "data/outputs/p95_baseline_multitable_raw.json"
TABLES = ("customers", "addresses", "products", "orders", "order_items")
Q01 = {"table": "order_items", "name": "idx_gt_q01_cover",
       "columns": ["product_id", "quantity", "unit_price"], "visible": "NO"}


def identifier(value):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError("Invalid SQL identifier")
    return f"`{value}`"


def validation_settings(path):
    # shortcut: chỉ đọc 3 scalar nguyên của validation; dùng parser YAML khi cần cấu hình phức tạp.
    text = path.read_text(encoding="utf-8")
    block = re.search(r"(?ms)^validation:[ \t]*\n(.*?)(?=^\S|\Z)", text)
    if block is None:
        raise ValueError("Missing validation settings")
    names = {"warmup_runs", "measured_runs", "min_p95_improvement_pct"}
    result = {}
    for line in block[1].splitlines():
        key = line.strip().split(":", 1)[0]
        if key in names:
            match = re.fullmatch(r"  ([a-z0-9_]+):[ \t]*(\d+)[ \t]*(?:#.*)?", line)
            if not match or key in result:
                raise ValueError("Validation settings require unique integer scalars")
            result[key] = int(match[2])
    if set(result) != names:
        raise ValueError("Incomplete validation settings")
    return result


def definitions(qid, candidate, wrong=False):
    result = []
    for n, (table, columns) in enumerate(candidate["wrong_indexes" if wrong else "indexes"]):
        if table not in TABLES or not 1 <= len(columns) <= 5:
            raise ValueError("Invalid index target")
        for col in columns:
            bits = col.split()
            identifier(bits[0])
            if len(bits) > 2 or (len(bits) == 2 and bits[1] not in ("ASC", "DESC")):
                raise ValueError("Invalid index direction")
        result.append({"table": table, "name": f"gt_trial_{qid}_{'bad' if wrong else 'good'}_{n}",
                       "columns": columns, "visible": "NO"})
    return result


def create_sql(spec):
    if spec["visible"] not in ("NO", "YES"):
        raise ValueError("Invalid visibility")
    columns = []
    for column in spec["columns"]:
        bits = column.split()
        columns.append(identifier(bits[0]) + (" " + bits[1] if len(bits) == 2 else ""))
    return (f"CREATE INDEX {identifier(spec['name'])} ON {identifier(spec['table'])} "
            f"({', '.join(columns)})" + (" INVISIBLE" if spec["visible"] == "NO" else ""))


def snapshot():
    indexes = []
    with get_conn() as conn, conn.cursor() as cur:
        for table in TABLES:
            cur.execute("SHOW INDEX FROM " + identifier(table))
            grouped = {}
            for row in cur.fetchall():
                spec = grouped.setdefault(row["Key_name"], {
                    "table": table, "name": row["Key_name"], "columns": [], "visible": row["Visible"],
                })
                spec["columns"].append(row["Column_name"] + (" DESC" if row["Collation"] == "D" else ""))
            indexes.extend(grouped.values())
    return indexes


def ddl(sql):
    # Đây là phép thử lab được người dùng cho phép, không phải đường apply của LLM.
    if Config.DB_ADMIN_USER != "index_admin":
        raise ValueError("DDL lab requires index_admin")
    conn = pymysql.connect(host=Config.DB_HOST, port=Config.DB_PORT,
                           user=Config.DB_ADMIN_USER, password=Config.DB_ADMIN_PASSWORD,
                           database=Config.DB_NAME, charset="utf8mb4", connect_timeout=10,
                           read_timeout=600, write_timeout=30)
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION lock_wait_timeout=30")
            cur.execute(sql)
    finally:
        conn.close()


def create(spec):
    sql = create_sql(spec)
    # sqlglot chưa parse INVISIBLE; AST kiểm tra CREATE, hậu tố hằng do script thêm.
    if not check(sql.removesuffix(" INVISIBLE"))[0]:
        raise ValueError("AST rejected index definition")
    print("CREATE", spec["table"], spec["name"], flush=True)
    ddl(sql)


def drop_owned(spec):
    actual = next((s for s in snapshot() if s["table"] == spec["table"] and s["name"] == spec["name"]), None)
    if actual is None:
        return
    if actual != spec:
        raise ValueError("Refuse to drop index whose definition changed")
    print("DROP", spec["name"], flush=True)
    ddl(f"DROP INDEX {identifier(spec['name'])} ON {identifier(spec['table'])}")


def restore_visible(expected):
    actual = snapshot()
    for spec in expected:
        if spec not in actual:
            if not spec["name"].startswith("fk_"):
                raise ValueError("Unexpected change to baseline index")
            if any(s["table"] == spec["table"] and s["name"] == spec["name"] for s in actual):
                raise ValueError("Baseline foreign key index definition changed")
            create(spec)


def read_plan(sql, invisible):
    if not check(sql)[0] or not isinstance(sqlglot.parse_one(sql, dialect="mysql"), exp.Select):
        raise ValueError("AST: only SELECT queries")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET SESSION MAX_EXECUTION_TIME=60000")
        cur.execute("SET SESSION time_zone='+00:00'")
        switch = "on" if invisible else "off"
        cur.execute(f"SET SESSION optimizer_switch='use_invisible_indexes={switch}'")
        cur.execute("EXPLAIN FORMAT=JSON " + sql)
        return json.loads(next(iter(cur.fetchone().values())))


def valid_measurement(entry, runs=20):
    return (entry.get("status") == "valid" and entry.get("runs", 0) >= runs
            and entry.get("timed_out_runs") == 0 and bool(entry.get("result_hash")))


def used_indexes(plan):
    if isinstance(plan, dict):
        found = {plan["key"]} if isinstance(plan.get("key"), str) else set()
        return found.union(*(used_indexes(v) for v in plan.values()))
    if isinstance(plan, list):
        return set().union(*(used_indexes(v) for v in plan))
    return set()


def optimized_sql(query, candidate, specs):
    sql = candidate.get("rewritten_sql", query["sql"])
    if not candidate.get("force_indexes") and not candidate.get("straight_join"):
        return sql
    tree = sqlglot.parse_one(sql, dialect="mysql")
    if candidate.get("force_indexes"):
        for table in tree.find_all(exp.Table):
            names = [s["name"] for s in specs if s["table"] == table.name]
            table.set("hints", [exp.IndexTableHint(this="FORCE", expressions=[exp.to_identifier(n) for n in names])] if names else None)
    if candidate.get("straight_join"):
        for join in tree.args.get("joins", []):
            if join.args.get("side") or join.args.get("kind") not in (None, "INNER"):
                raise ValueError("STRAIGHT_JOIN is only allowed for inner joins")
            join.set("kind", "STRAIGHT_JOIN")
    result = tree.sql(dialect="mysql")
    if not check(result)[0]:
        raise ValueError("AST rejected hinted SELECT")
    return result


def q30_edge_check(cursor, rewritten_sql):
    # SQLite không hỗ trợ LATERAL; CTE chỉ đọc kiểm tra trực tiếp trên MySQL, không tạo bảng.
    fixture = """WITH addresses(customer_id,city) AS (
        SELECT 1,'Ha Noi' UNION ALL SELECT 1,'Ha Noi' UNION ALL SELECT 2,'Da Nang' UNION ALL SELECT NULL,'Ha Noi'
    ), orders(order_id,customer_id,status) AS (
        SELECT 1,1,'paid' UNION ALL SELECT 2,1,'paid' UNION ALL SELECT 3,2,NULL
        UNION ALL SELECT 4,3,'cancelled' UNION ALL SELECT 5,NULL,'paid'
        UNION ALL SELECT 6,1,NULL UNION ALL SELECT 7,1,'shipped'
    ), order_items(order_id,unit_price) AS (
        SELECT 1,6000 UNION ALL SELECT 1,7000 UNION ALL SELECT 2,4000 UNION ALL SELECT 3,6000
        UNION ALL SELECT NULL,7000 UNION ALL SELECT 5,6000 UNION ALL SELECT 6,5001 UNION ALL SELECT 7,5000
    ) """
    results = []
    for sql in (get_query_by_id("q30")["sql"], rewritten_sql):
        if not check(fixture + sql)[0]:
            raise ValueError("AST rejected edge fixture")
        cursor.execute(fixture + sql)
        results.append(sorted(cursor.fetchall(), key=repr))
    expected = sorted([{"status": "paid", "n": 1}, {"status": None, "n": 1}], key=repr)
    if results != [expected, expected]:
        raise ValueError("q30 NULL/duplicate/boundary fixture mismatch")
    return {"passed": True, "cases": ["duplicate_addresses", "duplicate_items", "null_keys", "null_status", "price_5000_boundary"]}


def evaluate(before, after, threshold=20):
    if not valid_measurement(before) or not valid_measurement(after):
        return False, "incomplete_measurement"
    if before["result_hash"] != after["result_hash"] or before["row_count"] != after["row_count"]:
        return False, "result_mismatch"
    gain = 100 * (before["p95_ms"] - after["p95_ms"]) / before["p95_ms"]
    return (True, "passed") if gain >= threshold else (False, "insufficient_improvement")


def needs_fresh_baseline(before, after, threshold):
    # Mốc lịch sử có thể lệch theo tải; tín hiệu yếu cần đối chiếu cặp đo mới.
    _, reason = evaluate(before, after, threshold)
    if reason not in ("passed", "insufficient_improvement"):
        return False
    gain = 100 * (before["p95_ms"] - after["p95_ms"]) / before["p95_ms"]
    return gain < 2 * threshold


async def measure(sql, path, settings, *, invisible=True, screening=False):
    count = 5 if screening else settings["measured_runs"]
    response = json.loads(await benchmark_query(
        sql, warmup_runs=1 if screening else settings["warmup_runs"], measured_runs=count,
        timeout_ms=60000, use_invisible_indexes=invisible, compute_result_hash=True,
    ))
    data = response.get("data") or {}
    entry = dict(data, sql=sql, use_invisible_indexes=invisible, measured_at=now_iso(),
                 warmup_runs=1 if screening else settings["warmup_runs"],
                 status="valid" if response.get("ok") and data.get("runs") == count
                 and not data.get("timed_out_runs") and data.get("result_hash") else "invalid")
    if response.get("error"):
        entry["error"] = response["error"]
    save_output(path, entry)
    return entry


@contextmanager
def trial(specs, visible, report):
    if any(s["name"] == t["name"] and s["table"] == t["table"] for s in snapshot() for t in specs):
        raise ValueError("Trial index already exists; inspect interrupted run first")
    report["active_indexes"] = specs
    save_output(FOLDER / "report.json", report)
    try:
        for spec in specs:
            create(spec)
            restore_visible(visible)
        yield
    finally:
        for spec in reversed(specs):
            drop_owned(spec)
        restore_visible(visible)
        report["active_indexes"] = []
        save_output(FOLDER / "report.json", report)


def answer_for(candidate, specs, expected_type="index"):
    indexes = [{"type": "index", "table": s["table"], "index_name": s["name"],
                "columns": [c.split()[0] for c in s["columns"]],
                "directions": [c.split()[1] if len(c.split()) == 2 else "ASC" for c in s["columns"]]}
               for s in specs]
    if "rewritten_sql" in candidate and expected_type == "rewrite":
        answer = {"type": "rewrite", "rewritten_sql": candidate["rewritten_sql"], "required_indexes": indexes}
    else:
        answer = indexes[0] if len(indexes) == 1 else {"type": "index_set", "indexes": indexes}
        if "rewritten_sql" in candidate:
            answer.update(rewritten_sql=candidate["rewritten_sql"], requires_rewrite=True)
    if candidate.get("note"):
        answer["note"] = candidate["note"]
    return answer


def answer_index_specs(answer):
    if answer.get("type") not in ("index", "index_set", "rewrite"):
        raise ValueError("Unknown answer type")
    indexes = ([answer] if answer["type"] == "index" else
               answer.get("indexes", []) if answer["type"] == "index_set" else answer.get("required_indexes", []))
    result = []
    for index in indexes:
        directions = index.get("directions", ["ASC"] * len(index["columns"]))
        if len(directions) != len(index["columns"]) or any(d not in ("ASC", "DESC") for d in directions):
            raise ValueError("Invalid stored index direction")
        result.append({"table": index["table"], "name": index["index_name"],
                       "columns": [c + (" DESC" if d == "DESC" else "") for c, d in zip(index["columns"], directions, strict=True)],
                       "visible": "NO"})
    return sorted(result, key=lambda s: (s["table"], s["name"]))


def same_counterfactual_sql(first, second):
    normalized = []
    for sql in (first, second):
        tree = sqlglot.parse_one(sql, dialect="mysql")
        for hint in tree.find_all(exp.IndexTableHint):
            for name in hint.expressions:
                if name.name.startswith("gt_trial_"):
                    name.set("this", "trial_index")
        normalized.append(tree.sql(dialect="mysql"))
    return normalized[0] == normalized[1]


def audit():
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    report_path = ROOT / "data/outputs/ground_truth_validation/report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    failures = []
    for q in QUERIES:
        entry = truth["queries"][q["id"]]
        m = entry.get("measurement", {})
        try:
            bpath, apath = ROOT / m["before_result_file"], ROOT / m["after_result_file"]
            before, after = json.loads(bpath.read_text(encoding="utf-8")), json.loads(apath.read_text(encoding="utf-8"))
            if "results" in before:
                before = before["results"][q["id"]]
            if "results" in after:
                after = after["results"][q["id"]]
            ok, reason = evaluate(before, after)
            if before.get("sql") != q["sql"] or not entry["acceptable_answers"]:
                ok, reason = False, "sql_or_answer_missing"
            expected_sql = [a.get("rewritten_sql", q["sql"]) for a in entry["acceptable_answers"]]
            if after.get("sql") not in expected_sql:
                ok, reason = False, "after_sql_does_not_match_answer"
            if (after.get("sql") != q["sql"]
                    and any(a["type"] in ("index", "index_set") and a.get("requires_rewrite") is not True
                            for a in entry["acceptable_answers"])):
                ok, reason = False, "required_rewrite_flag_missing"
            if len(entry["acceptable_answers"]) != 1:
                ok, reason = False, "each_answer_needs_separate_evidence"
            elif q["id"] == "q01":
                if answer_index_specs(entry["acceptable_answers"][0]) != [Q01]:
                    ok, reason = False, "index_definition_does_not_match_evidence"
            else:
                proofs = [report.get("results", {}).get(q["id"], {})]
                proofs += [p for p in report.get("history", []) if p.get("query_id") == q["id"]]
                expected_indexes = answer_index_specs(entry["acceptable_answers"][0])
                if not any(p.get("accepted") and p.get("after") == after
                           and sorted(p.get("effective_indexes", []), key=lambda s: (s["table"], s["name"])) == expected_indexes
                           for p in proofs):
                    ok, reason = False, "index_definition_does_not_match_evidence"
            if before["p95_ms"] != m["before_p95_ms"] or after["p95_ms"] != m["after_p95_ms"]:
                ok, reason = False, "stored_measurement_mismatch"
            if (m.get("before_result_hash") != before.get("result_hash")
                    or m.get("after_result_hash") != after.get("result_hash")
                    or m.get("before_row_count") != before.get("row_count")
                    or m.get("after_row_count") != after.get("row_count")):
                ok, reason = False, "stored_hash_or_count_mismatch"
            gain = 100 * (before["p95_ms"] - after["p95_ms"]) / before["p95_ms"]
            if m.get("improvement_pct") != round(gain, 2):
                ok, reason = False, "stored_improvement_mismatch"
            if before.get("use_invisible_indexes", False) or not after.get("use_invisible_indexes", False):
                ok, reason = False, "optimizer_mode_mismatch"
            if q.get("group") == 2:
                comparison = entry["composite_order_check"]
                wrong = json.loads((ROOT / comparison["evidence_file"]).read_text(encoding="utf-8"))
                order_ok, _ = evaluate(wrong, after)
                if (not order_ok or comparison.get("passed") is not True
                        or comparison.get("wrong_order_p95_ms") != wrong["p95_ms"]
                        or not same_counterfactual_sql(wrong["sql"], after["sql"])):
                    ok, reason = False, "composite_order_comparison_not_verified"
            if not ok:
                failures.append((q["id"], reason))
            print(q["id"], "PASS" if ok else reason, flush=True)
        except (KeyError, OSError, ValueError) as exc:
            failures.append((q["id"], type(exc).__name__))
            print(q["id"], "NOT_VERIFIED", flush=True)
    print(f"Evidence audit: {len(QUERIES)-len(failures)}/{len(QUERIES)} passed; expert review remains separate.")
    return int(bool(failures))


async def run(args):
    if Config.DB_USER != "readonly_user":
        raise ValueError("SELECT requires readonly_user")
    settings = validation_settings(ROOT / "config/settings.yaml")
    if settings["measured_runs"] < 20 or settings["warmup_runs"] < 3 or settings["min_p95_improvement_pct"] < 20:
        raise ValueError("Validation settings below required quality bar")
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    report_path = FOLDER / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {"results": {}}
    if report.get("active_indexes"):
        raise ValueError("Interrupted run left active indexes; inspect report before resuming")
    original = snapshot()
    visible = [s for s in original if s["visible"] == "YES"]
    invisible = [s for s in original if s["visible"] == "NO"]
    if invisible != [Q01]:
        raise ValueError("Expected only the known q01 invisible index before batch")
    report["visible_indexes"] = visible
    report["settings"] = settings
    save_output(report_path, report)
    try:
        drop_owned(Q01)
        for qid in args.ids or list(CANDIDATES):
            if qid not in CANDIDATES:
                raise ValueError("Only q02-q30 are batch candidates")
            candidate = dict(CANDIDATES[qid])
            query = get_query_by_id(qid)
            signature = hashlib.sha256(json.dumps([query["sql"], candidate], sort_keys=True).encode()).hexdigest()
            old = report["results"].get(qid, {})
            if old.get("signature") == signature and old.get("accepted") and not args.force:
                print(qid, "SKIP VERIFIED", flush=True)
                continue
            before = baseline["results"][qid]
            before_file = str(BASELINE.relative_to(ROOT)).replace('\\', '/')
            if not valid_measurement(before) or before.get("sql") != query["sql"]:
                raise ValueError("Baseline missing or stale for " + qid)
            print("\nVERIFY", qid, "group", query["group"], flush=True)
            run_dir = FOLDER / qid / f"{signature[:10]}_{time.time_ns()}"
            after_file = (run_dir / "after.json").relative_to(ROOT).as_posix()
            specs = definitions(qid, candidate)
            optimized = optimized_sql(query, candidate, specs)
            before_plan = read_plan(query["sql"], False)
            result = {"signature": signature, "candidate": candidate, "before": before,
                      "before_plan": before_plan, "accepted": False}
            if qid == "q30":
                with get_conn() as conn, conn.cursor() as cur:
                    result["edge_check"] = q30_edge_check(cur, candidate["rewritten_sql"])
            with trial(specs, visible, report):
                result["after_plan"] = read_plan(optimized, True)
                result["initial_after_plan"] = result["after_plan"]
                used = used_indexes(result["after_plan"])
                effective = [s for s in specs if s["name"] in used]
                for unused in [s for s in specs if s not in effective]:
                    drop_owned(unused)
                if candidate.get("force_indexes"):
                    optimized = optimized_sql(query, candidate, effective)
                if optimized != query["sql"]:
                    candidate["rewritten_sql"] = optimized
                result["effective_indexes"] = effective
                result["after_plan"] = read_plan(optimized, True)
                if not effective and optimized == query["sql"]:
                    result["reason"] = "optimizer_did_not_choose_proposed_index"
                else:
                    screen = await measure(optimized, run_dir / "screen.json", settings, screening=True)
                    result["screening"] = screen
                    gain = 100 * (before["p95_ms"] - screen.get("p95_ms", before["p95_ms"])) / before["p95_ms"]
                    median_gain = 100 * (before["p50_ms"] - screen.get("p50_ms", before["p50_ms"])) / before["p50_ms"]
                    if (valid_measurement(screen, 5) and screen["result_hash"] == before["result_hash"]
                            and max(gain, median_gain) >= settings["min_p95_improvement_pct"]):
                        after = await measure(optimized, ROOT / after_file, settings)
                        result["after"] = after
                        result["after_file"] = after_file
                        result["accepted"], result["reason"] = evaluate(before, after, settings["min_p95_improvement_pct"])
                        improvement = 100 * (before["p95_ms"] - after.get("p95_ms", before["p95_ms"])) / before["p95_ms"]
                        if needs_fresh_baseline(before, after, settings["min_p95_improvement_pct"]):
                            print(qid, "REMEASURE BEFORE: historical baseline needs paired check", flush=True)
                            before_file = (run_dir / "before.json").relative_to(ROOT).as_posix()
                            before = await measure(query["sql"], ROOT / before_file, settings, invisible=False)
                            result["before"] = before
                            result["accepted"], result["reason"] = evaluate(before, after, settings["min_p95_improvement_pct"])
                    else:
                        result["reason"] = "screening_failed_or_below_threshold"
            if result["accepted"] and "wrong_indexes" in candidate:
                wrong_specs = definitions(qid, candidate, wrong=True)
                with trial(wrong_specs, visible, report):
                    wrong_sql = optimized_sql(query, CANDIDATES[qid], wrong_specs)
                    wrong_file = (run_dir / "wrong_order.json").relative_to(ROOT).as_posix()
                    wrong = await measure(wrong_sql, ROOT / wrong_file, settings)
                    result["wrong_order"] = wrong
                    result["wrong_order_plan"] = read_plan(wrong_sql, True)
                result["order_comparison_passed"], result["order_reason"] = evaluate(wrong, result["after"], settings["min_p95_improvement_pct"])
                if not result["order_comparison_passed"]:
                    result["accepted"], result["reason"] = False, "composite_order_comparison_not_verified"
            if result["accepted"]:
                after = result["after"]
                improvement = 100 * (before["p95_ms"] - after["p95_ms"]) / before["p95_ms"]
                truth = json.loads(TRUTH.read_text(encoding="utf-8"))
                entry = truth["queries"][qid]
                entry["acceptable_answers"] = [answer_for(candidate, result["effective_indexes"], query["expected_answer_type"])]
                entry["verification_status"] = "performance_verified_pending_review"
                entry["measurement"] = {
                    "before_p95_ms": before["p95_ms"], "after_p95_ms": after["p95_ms"],
                    "improvement_pct": round(improvement, 2), "measured_runs": settings["measured_runs"],
                    "warmup_runs": settings["warmup_runs"], "timeout_ms": 60000, "cache_state": "warm",
                    "before_timed_out_runs": 0, "after_timed_out_runs": 0, "result_equivalent": True,
                    "before_result_hash": before["result_hash"], "after_result_hash": after["result_hash"],
                    "before_row_count": before["row_count"], "after_row_count": after["row_count"],
                    "before_result_file": before_file,
                    "after_result_file": after_file,
                    "measured_by": "Codex (lab execution authorized by user)", "measured_at": after["measured_at"],
                    "baseline_reused": before_file == str(BASELINE.relative_to(ROOT)).replace('\\', '/'),
                    "trial_indexes_persisted": False,
                }
                entry["explain_check"] = {
                    "before_query_cost": before_plan.get("query_block", {}).get("cost_info", {}).get("query_cost"),
                    "after_query_cost": result["after_plan"].get("query_block", {}).get("cost_info", {}).get("query_cost"),
                    "before_selected_indexes": sorted(used_indexes(before_plan)),
                    "after_selected_indexes": sorted(used_indexes(result["after_plan"])),
                    "evidence_file": "data/outputs/ground_truth_validation/report.json",
                }
                if "order_comparison_passed" in result:
                    entry["composite_order_check"] = {"passed": result["order_comparison_passed"],
                                                       "reason": result["order_reason"],
                                                       "wrong_order_p95_ms": result["wrong_order"].get("p95_ms"),
                                                       "evidence_file": wrong_file}
                count = sum(bool(v["acceptable_answers"]) for v in truth["queries"].values())
                truth["verification_status"] = "performance_verified_pending_review" if count == len(QUERIES) else "partial_performance_verified_pending_review"
                truth["notes"] = f"{count}/30 query có phương án đạt kiểm chứng P95/hash, còn chờ Hải review; không khẳng định tối ưu toàn cục. Đáp án có rewritten_sql/required_indexes/requires_rewrite phải dùng đủ SQL và index kèm theo. Các gt_trial index được dọn sau đo. Kiểm tra composite_order_check cho nhóm 2. Chưa đo đầy đủ chi phí ghi/dung lượng."
                save_output(TRUTH, truth)
                print(qid, "ACCEPT", round(improvement, 2), "%", flush=True)
            else:
                print(qid, "NOT ACCEPTED", result["reason"], flush=True)
            if old:
                report.setdefault("history", []).append(dict(old, query_id=qid))
            report["results"][qid] = result
            save_output(report_path, report)
    finally:
        if Q01 not in snapshot():
            create(Q01)
        restore_visible(visible)
        if sorted(snapshot(), key=lambda s: (s["table"], s["name"])) != sorted(original, key=lambda s: (s["table"], s["name"])):
            raise ValueError("Final index configuration does not match initial snapshot")
        print("RESTORED original index configuration", flush=True)
    return audit()


def main():
    parser = argparse.ArgumentParser(description="Verify ground truth candidates in the authorized MySQL lab")
    parser.add_argument("--ids", nargs="+", choices=list(CANDIDATES))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true", help="Offline evidence audit; does not connect to MySQL")
    args = parser.parse_args()
    return audit() if args.check else asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
