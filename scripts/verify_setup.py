"""
Script verify 6 file nền tảng + kết nối MySQL.
Chạy: python scripts/verify_setup.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("🔍 VERIFY SETUP — MCP Slow Query Optimizer")
print("=" * 60)
print()

# Test 1: Import config
try:
    from mcp_server.utils.config import Config
    print("✅ Config import OK")
    print(f"   DB_HOST = {Config.DB_HOST}")
    print(f"   DB_PORT = {Config.DB_PORT}")
    print(f"   DB_NAME = {Config.DB_NAME}")
except Exception as e:
    print(f"❌ Config LỖI: {e}")
    sys.exit(1)

# Test 2: Import db
try:
    from mcp_server.utils.db import get_conn, get_admin_conn
    print("✅ DB import OK")
except Exception as e:
    print(f"❌ DB LỖI: {e}")
    sys.exit(1)

# Test 3: Import logger
try:
    from mcp_server.utils.logger import get_logger
    print("✅ Logger import OK")
except Exception as e:
    print(f"❌ Logger LỖI: {e}")
    sys.exit(1)

print()
print("=" * 60)
print("🔌 TEST KẾT NỐI MYSQL")
print("=" * 60)

# Test 4: Kết nối readonly
try:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM sales_data")
            result = cur.fetchone()
            print(f"✅ Kết nối readonly OK")
            print(f"   Total rows: {result['total']:,}")
except Exception as e:
    print(f"❌ Kết nối readonly LỖI: {e}")
    sys.exit(1)

# Test 5: Kết nối admin
try:
    with get_admin_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT USER() AS u")
            result = cur.fetchone()
            print(f"✅ Kết nối admin OK")
            print(f"   User: {result['u']}")
except Exception as e:
    print(f"⚠️  Kết nối admin LỖI: {e}")
    print(f"   (Không ảnh hưởng Tool 1-5)")

# Test 6: Verify cấu trúc bảng
try:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DESCRIBE sales_data")
            cols = cur.fetchall()
            print(f"✅ Bảng sales_data có {len(cols)} cột")
except Exception as e:
    print(f"❌ Lỗi check bảng: {e}")

print()
print("=" * 60)
print("🎉 HOÀN TẤT — NỀN TẢNG SẴN SÀNG")
print("=" * 60)