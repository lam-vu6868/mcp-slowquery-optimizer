"""
Script kiểm tra toàn bộ setup đã sẵn sàng chạy dự án chưa.
Chạy: python scripts/verify_setup.py
"""
import os
import sys
import subprocess
from pathlib import Path

# ANSI colors cho Windows
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def ok(msg): print(f"{GREEN}✅ {msg}{RESET}")
def fail(msg): print(f"{RED}❌ {msg}{RESET}")
def warn(msg): print(f"{YELLOW}⚠️  {msg}{RESET}")
def info(msg): print(f"{BLUE}ℹ️  {msg}{RESET}")


def check_python_version():
    """Kiểm tra Python >= 3.11"""
    print("\n[1/8] Kiểm tra Python version...")
    v = sys.version_info
    if v.major == 3 and v.minor >= 11:
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
        return True
    fail(f"Python {v.major}.{v.minor} — cần >= 3.11")
    return False


def check_files():
    """Kiểm tra file quan trọng tồn tại"""
    print("\n[2/8] Kiểm tra file quan trọng...")
    required = [
        "requirements.txt",
        "docker-compose.yml",
        ".gitignore",
        ".env.example",
        "db/schema.sql",
        "db/init.sql",
        "db/conf/my.cnf",
        "dashboard/app.py",
        "README.md",
    ]
    missing = []
    for f in required:
        if not Path(f).exists():
            missing.append(f)
            fail(f"Thiếu: {f}")
        else:
            ok(f"{f}")
    return len(missing) == 0


def check_env_file():
    """Kiểm tra .env đã tạo chưa + có API key chưa"""
    print("\n[3/8] Kiểm tra file .env...")
    env = Path(".env")
    if not env.exists():
        fail(".env CHƯA TẠO — chạy: copy .env.example .env")
        return False
    ok(".env tồn tại")

    content = env.read_text(encoding="utf-8")
    checks = {
        "ANTHROPIC_API_KEY": "sk-ant-",
        "APPROVAL_SECRET": None,
    }
    all_ok = True
    for key, prefix in checks.items():
        line = [l for l in content.splitlines() if l.startswith(key)]
        if not line:
            fail(f"{key} chưa có trong .env")
            all_ok = False
            continue
        value = line[0].split("=", 1)[1].strip()
        if not value or "CHANGE_ME" in value or value.startswith("sk-ant-xxx"):
            fail(f"{key} chưa điền giá trị thật")
            all_ok = False
        else:
            ok(f"{key} đã điền")
    return all_ok


def check_python_deps():
    """Kiểm tra các thư viện Python quan trọng"""
    print("\n[4/8] Kiểm tra thư viện Python...")
    deps = [
        ("mcp", "MCP SDK"),
        ("pymysql", "MySQL driver"),
        ("sqlglot", "SQL parser"),
        ("anthropic", "Claude API"),
        ("streamlit", "Dashboard"),
        ("pandas", "DataFrame"),
        ("matplotlib", "Charts"),
        ("faker", "Seed data"),
        ("dotenv", "Env loader"),
        ("pytest", "Testing"),
    ]
    missing = []
    for mod, name in deps:
        try:
            __import__(mod)
            ok(f"{mod} ({name})")
        except ImportError:
            fail(f"{mod} ({name}) — chưa cài")
            missing.append(mod)
    if missing:
        info(f"Chạy: pip install -r requirements.txt")
    return len(missing) == 0


def check_docker():
    """Kiểm tra Docker đã cài + MySQL container chạy chưa"""
    print("\n[5/8] Kiểm tra Docker...")
    try:
        r = subprocess.run(
            ["docker", "--version"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode != 0:
            fail("Docker chưa cài")
            return False
        ok(f"Docker: {r.stdout.strip()}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        fail("Docker chưa cài hoặc không chạy")
        return False

    try:
        r = subprocess.run(
            ["docker", "ps", "--filter", "name=shopdb", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5
        )
        if "shopdb" in r.stdout:
            ok("MySQL container 'shopdb' đang chạy")
        else:
            warn("MySQL container chưa chạy — chạy: docker compose up -d")
    except Exception as e:
        warn(f"Không check được container: {e}")
    return True


def check_mysql_connection():
    """Kiểm tra kết nối MySQL + user + slow log"""
    print("\n[6/8] Kiểm tra kết nối MySQL...")
    try:
        import pymysql
        from dotenv import load_dotenv
        load_dotenv()

        conn = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "readonly_user"),
            password=os.getenv("DB_PASSWORD", "readonly_pass"),
            database=os.getenv("DB_NAME", "shopdb"),
            connect_timeout=5,
        )
        ok("Kết nối MySQL (readonly_user) OK")

        with conn.cursor() as cur:
            cur.execute("SHOW VARIABLES LIKE 'slow_query_log'")
            row = cur.fetchone()
            if row and row[1] == "ON":
                ok("slow_query_log = ON")
            else:
                fail(f"slow_query_log = {row[1] if row else '?'}")

            cur.execute("SHOW VARIABLES LIKE 'log_output'")
            row = cur.fetchone()
            if row and "TABLE" in row[1]:
                ok(f"log_output = {row[1]}")
            else:
                warn(f"log_output = {row[1] if row else '?'} — nên là FILE,TABLE")

        conn.close()
        return True
    except Exception as e:
        fail(f"Không kết nối được MySQL: {e}")
        info("Kiểm tra: docker compose up -d && đợi 15s")
        return False


def check_git():
    """Kiểm tra Git đã init + branch hiện tại"""
    print("\n[7/8] Kiểm tra Git...")
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        branch = r.stdout.strip()
        ok(f"Branch hiện tại: {branch}")
        if branch not in ("dev", "main"):
            warn(f"Đang ở branch '{branch}' — nhánh chính là 'dev'/'main'")

        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5
        )
        if r.stdout.strip():
            changed = len(r.stdout.strip().splitlines())
            warn(f"Có {changed} file chưa commit")
        else:
            ok("Working tree sạch")
        return True
    except Exception as e:
        fail(f"Git lỗi: {e}")
        return False


def check_directory_structure():
    """Kiểm tra cấu trúc thư mục"""
    print("\n[8/8] Kiểm tra cấu trúc thư mục...")
    dirs = [
        "mcp_server", "mcp_server/tools", "mcp_server/llm",
        "mcp_server/validation", "mcp_server/utils",
        "db", "db/conf", "data", "data/seed", "data/queries",
        "data/metrics", "security", "security/injection_tests",
        "dashboard", "dashboard/pages", "tests", "docs",
        "reports", "scripts", ".github/workflows",
    ]
    missing = [d for d in dirs if not Path(d).is_dir()]
    if missing:
        for d in missing:
            fail(f"Thiếu thư mục: {d}")
        return False
    ok(f"Đầy đủ {len(dirs)} thư mục")
    return True


def main():
    print("=" * 60)
    print("  🔍 VERIFY SETUP — MCP SLOW QUERY OPTIMIZER")
    print("=" * 60)

    results = {
        "Python": check_python_version(),
        "Files": check_files(),
        ".env": check_env_file(),
        "Deps": check_python_deps(),
        "Docker": check_docker(),
        "MySQL": check_mysql_connection(),
        "Git": check_git(),
        "Dirs": check_directory_structure(),
    }

    print("\n" + "=" * 60)
    print("  📊 KẾT QUẢ")
    print("=" * 60)
    for name, passed in results.items():
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {name:15} [{status}]")

    total = len(results)
    passed = sum(results.values())
    print(f"\n  {passed}/{total} hạng mục đạt")

    if passed == total:
        print(f"\n{GREEN}🎉 SETUP HOÀN CHỈNH — Sẵn sàng code!{RESET}")
        return 0
    else:
        print(f"\n{YELLOW}⚠️  Còn {total - passed} hạng mục cần fix — xem hướng dẫn bên trên{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())