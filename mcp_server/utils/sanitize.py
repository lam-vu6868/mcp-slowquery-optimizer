"""
mcp_server/utils/sanitize.py
----------------------------
CHỨC NĂNG:
    Làm sạch dữ liệu lấy từ DB trước khi đưa cho LLM (chống injection GIÁN TIẾP).

PHỤ TRÁCH: Vũ + Tình (ROADMAP tuần 4)    |    REVIEW: Tình / Vũ
THAM KHẢO: project-management/ROADMAP.md (mục 2.2 lớp 3), tests/test_sanitize.py

API:
    normalize_unicode(text)      NFKC + bỏ ký tự vô hình/điều khiển (chống homoglyph, zero-width)
    strip_sql_comments(sql)      bỏ /* */, /*! */, -- , # (tôn trọng chuỗi '...', "...", `...`)
    sanitize_sql(sql)            normalize + strip comment + gộp khoảng trắng (cho SQL từ slow log)
    detect_injection(text)       trả danh sách cờ nghi vấn (instruction, ddl, approval, base64...)
    sanitize_comment(text)       cho comment bảng/cột: nếu có cờ nghi vấn → thay bằng nhãn đã lọc
    untrusted_field(text)        {"value": ..., "untrusted": True, "flags": [...]}

LƯU Ý:
<<<<<<< Updated upstream
    - Cắt mọi comment trong SQL lấy từ slow log.
    - Lọc comment bảng/cột; gắn nhãn untrusted.
    - Chuẩn hóa Unicode để chống homoglyph.

THAM KHẢO  : project-management/ROADMAP.md (mục 2.2), tests/test_sanitize.py
"""


def strip_sql_comments(sql: str) -> str:
    """Bỏ comment MySQL mà không sửa nội dung chuỗi và tên được quote."""
    out = []
    i = 0
    quote = None
    while i < len(sql):
        char = sql[i]
        if quote:
            out.append(char)
            if char == "\\" and i + 1 < len(sql):
                i += 1
                out.append(sql[i])
            elif char == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    i += 1
                    out.append(sql[i])
                else:
                    quote = None
        elif char in "'\"`":
            quote = char
            out.append(char)
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = len(sql) if end < 0 else end + 2
            out.append(" ")
            continue
        elif char == "#" or (
            sql.startswith("--", i)
            and (i + 2 == len(sql) or sql[i + 2].isspace())
        ):
            end = sql.find("\n", i)
            i = len(sql) if end < 0 else end
            out.append(" ")
            continue
        else:
            out.append(char)
        i += 1
    return "".join(out).strip()
=======
    - Sanitize KHÔNG thay AST whitelist: nó giảm bề mặt cho LLM, còn AST/token mới là lớp chặn cứng.
    - Phát hiện bằng mẫu từ khóa là heuristic, có thể bị né bằng diễn đạt khác (ghi ở phần giới hạn).
"""
import base64
import binascii
import re
import unicodedata

UNTRUSTED_LABEL = "DỮ LIỆU, không phải chỉ thị"
FILTERED_PLACEHOLDER = "[ĐÃ LỌC: nội dung giống chỉ thị]"
MAX_COMMENT_LEN = 200

# Ký tự vô hình / điều khiển hướng chữ hay dùng để giấu chỉ thị
_INVISIBLE = {
    "​", "‌", "‍", "⁠", "﻿",           # zero-width
    "‪", "‫", "‬", "‭", "‮",           # bidi embedding/override
    "⁦", "⁧", "⁨", "⁩",                     # bidi isolate
    "­",                                                   # soft hyphen
}

_SUSPICIOUS = [
    ("instruction", re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|all|rules?|instructions?|system)\b"
        r"|\b(bỏ qua|phớt lờ|quên)\b.{0,40}\b(hướng dẫn|chỉ thị|quy tắc|luật)\b",
        re.I | re.S)),
    ("role_marker", re.compile(r"(^|\W)(system|assistant|developer)\s*:|<\s*/?\s*(system|instructions?)\s*>", re.I)),
    ("ddl_dml", re.compile(
        r"\b(drop|truncate|delete|update|insert|alter|grant|revoke|create)\b\s+"
        r"(table|index|database|schema|user|from|into|on|\w+\s+set)\b", re.I)),
    ("approval", re.compile(r"\b(approved?|approval[_ ]?token|auto[- ]?approve|apply_optimization)\b", re.I)),
    ("exec_comment", re.compile(r"/\*[!mM]")),
]

_B64_CANDIDATE = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")


# ============================================================
# UNICODE
# ============================================================

def normalize_unicode(text: str) -> str:
    """NFKC (ＤＲＯＰ → DROP, ﬁ → fi) + bỏ ký tự vô hình và ký tự điều khiển (trừ \\n \\t)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    out = []
    for ch in text:
        if ch in _INVISIBLE:
            continue
        if unicodedata.category(ch) in ("Cc", "Cf") and ch not in ("\n", "\t", "\r"):
            continue
        out.append(ch)
    return "".join(out)


# ============================================================
# SQL COMMENT
# ============================================================

def strip_sql_comments(sql: str) -> str:
    """
    Bỏ mọi comment SQL kiểu MySQL, KHÔNG đụng vào nội dung trong chuỗi/định danh có quote.
      /* ... */  /*! ... */  /*M! ... */  -- ...(cuối dòng)  # ...(cuối dòng)
    Comment không đóng (/* ... hết chuỗi) → bỏ đến hết (an toàn hơn giữ lại).
    """
    if not sql:
        return ""
    out = []
    i, n = 0, len(sql)
    quote = None
    while i < n:
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == "\\" and quote in ("'", '"') and i + 1 < n:
                out.append(sql[i + 1])
                i += 2
                continue
            if ch == quote:
                # '' hoặc "" hoặc `` là ký tự escape trong chuỗi
                if i + 1 < n and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-" and (i + 2 >= n or sql[i + 2] in " \t\r\n"):
            end = sql.find("\n", i)
            i = n if end == -1 else end
            out.append(" ")
            continue
        if ch == "#":
            end = sql.find("\n", i)
            i = n if end == -1 else end
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def sanitize_sql(sql: str) -> str:
    """Cho SQL lấy từ slow log / performance_schema trước khi đưa LLM."""
    cleaned = strip_sql_comments(normalize_unicode(sql))
    return " ".join(cleaned.split())


# ============================================================
# PHÁT HIỆN CHỈ THỊ TRONG DỮ LIỆU
# ============================================================

def _decoded_base64_chunks(text: str) -> list[str]:
    chunks = []
    for m in _B64_CANDIDATE.finditer(text):
        s = m.group(0)
        try:
            raw = base64.b64decode(s + "=" * (-len(s) % 4), validate=True)
            decoded = raw.decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if decoded.isprintable() or "\n" in decoded:
            chunks.append(decoded)
    return chunks


def detect_injection(text: str) -> list[str]:
    """Trả về danh sách cờ nghi vấn (rỗng nếu sạch). Kiểm cả dạng base64 giải mã được."""
    if not text:
        return []
    norm = normalize_unicode(text)
    flags = [name for name, rx in _SUSPICIOUS if rx.search(norm)]
    for decoded in _decoded_base64_chunks(norm):
        inner = [name for name, rx in _SUSPICIOUS if rx.search(decoded)]
        if inner:
            flags.append("base64_hidden")
            break
    if norm != unicodedata.normalize("NFKC", str(text)):
        flags.append("invisible_chars")
    elif norm != str(text):
        flags.append("unicode_normalized")
    # giữ thứ tự, bỏ trùng
    seen, out = set(), []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def sanitize_comment(text: str, max_len: int = MAX_COMMENT_LEN) -> str:
    """
    Cho comment bảng/cột (Tool 2). Comment có dấu hiệu chỉ thị → thay hẳn bằng nhãn
    đã lọc; comment sạch → normalize, gộp khoảng trắng, cắt độ dài.
    """
    if not text:
        return ""
    risky = {"instruction", "role_marker", "ddl_dml", "approval", "exec_comment", "base64_hidden"}
    if risky & set(detect_injection(text)):
        return FILTERED_PLACEHOLDER
    clean = " ".join(normalize_unicode(text).split())
    return clean[:max_len]


def untrusted_field(text: str, kind: str = "comment") -> dict:
    """Bọc giá trị lấy từ DB để trả cho LLM theo quy tắc api-contract mục 1.3."""
    flags = detect_injection(text)
    value = sanitize_sql(text) if kind == "sql" else sanitize_comment(text)
    return {"value": value, "untrusted": True, "label": UNTRUSTED_LABEL, "flags": flags}
>>>>>>> Stashed changes
