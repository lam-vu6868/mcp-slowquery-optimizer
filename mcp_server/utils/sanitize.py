"""
mcp_server/utils/sanitize.py
----------------------------

CHỨC NĂNG :
    Làm sạch dữ liệu lấy từ DB trước khi đưa cho LLM (chống injection gián tiếp).

PHỤ TRÁCH  : Vũ    |    REVIEW: Tình

LƯU Ý:
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
