import os
import re

USE_POSTGRES = bool(os.environ.get("DATABASE_URL"))
PLACEHOLDER = "%s" if USE_POSTGRES else "?"

if USE_POSTGRES:
    import psycopg

    def get_conn():
        url = os.environ["DATABASE_URL"]
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg.connect(url)
else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "students.db")

    def get_conn():
        return sqlite3.connect(DB_PATH)


def split_statements(text):
    stmts, buf, in_str = [], [], False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_str:
            buf.append(ch)
            if ch == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    buf.append("'")
                    i += 1
                else:
                    in_str = False
        elif ch == "'":
            in_str = True
            buf.append(ch)
        elif ch == ";":
            stmts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return [s.strip() for s in stmts if s.strip()]


def run_sql(sql_text):
    results = []
    conn = get_conn()
    error_happened = False
    try:
        for stmt in split_statements(sql_text):
            entry = {"sql": stmt}
            md = _DESC_RE.match(stmt)
            if md:
                info = describe_table(md.group(1))
                if info is None:
                    entry.update(type="error", text=f"ERROR: table or view does not exist: {md.group(1)}")
                    results.append(entry)
                    break
                entry.update(type="rows", columns=["Name", "Null?", "Type"], rows=info)
                results.append(entry)
                continue
            if _SQLPLUS_RE.match(stmt):
                entry.update(type="status", text="(SQL*Plus formatting command ignored)")
                results.append(entry)
                continue
            if _PLSQL_RE.match(stmt):
                entry.update(
                    type="error",
                    text="PL/SQL blocks are not supported on this console.\n"
                    "Run plain SQL statements (SELECT / INSERT / UPDATE / DELETE ...) instead.",
                )
                results.append(entry)
                break
            translated = oracle_compat(stmt)
            try:
                if not USE_POSTGRES and stmt.upper() == "COMMIT":
                    conn.commit()
                    entry.update(type="status", text="Commit complete.")
                    results.append(entry)
                    continue
                if not USE_POSTGRES and stmt.upper() == "ROLLBACK":
                    conn.rollback()
                    entry.update(type="status", text="Rollback complete.")
                    results.append(entry)
                    continue
                cur = conn.execute(translated)
                if cur.description:
                    cols = [d[0] for d in cur.description]
                    rows = [tuple(r) for r in cur.fetchall()]
                    entry.update(type="rows", columns=cols, rows=rows)
                elif cur.rowcount >= 0:
                    n = cur.rowcount
                    word = "row" if n == 1 else "rows"
                    entry.update(type="status", text=f"{n} {word} affected.")
                else:
                    entry.update(type="status", text="Command executed successfully.")
            except Exception as exc:
                entry.update(type="error", text=f"{exc.__class__.__name__}: {exc}")
                error_happened = True
            results.append(entry)
            if error_happened:
                break
        if error_happened:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()
    return results


IDENT_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_DESC_RE = re.compile(r"^\s*DESC(?:RIBE)?\s+([A-Za-z_][A-Za-z0-9_]*)\s*;?\s*$", re.I)
_SQLPLUS_RE = re.compile(
    r"^\s*(SET|SPOOL|SHOW|PROMPT|PAUSE|COLUMN|TTITLE|BTITLE|BREAK|COMPUTE|CLEAR|EXIT|QUIT)\b",
    re.I,
)
_PLSQL_RE = re.compile(r"^\s*(DECLARE|BEGIN)\b", re.I)

_ORACLE_RULES = [
    (r"\bVARCHAR2\s*\(", "VARCHAR(", re.I),
    (r"\bNUMBER\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", lambda m: f"NUMERIC({m.group(1)},{m.group(2)})", re.I),
    (r"\bNUMBER\s*\(\s*(\d+)\s*\)", lambda m: f"NUMERIC({m.group(1)})", re.I),
    (r"\bNUMBER\b", "NUMERIC", re.I),
    (r"\bSYSDATE\b", "CURRENT_TIMESTAMP", re.I),
    (r"\bNVL\s*\(", "COALESCE(", re.I),
    (r"\bMINUS\b", "EXCEPT", re.I),
    (r"\bDATE\b", "TIMESTAMP", 0),
    (
        r"\bLISTAGG\s*\(([^()]*?)\)\s*WITHIN\s+GROUP\s*\(\s*ORDER\s+BY\s+([^()]*?)\s*\)",
        r"STRING_AGG(\1 ORDER BY \2)",
        re.I,
    ),
]


def _find_close(s, open_idx):
    depth = 0
    for k in range(open_idx, len(s)):
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _split_top_args(argstr):
    args, cur, depth = [], "", 0
    for c in argstr:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += c
    if cur.strip():
        args.append(cur.strip())
    return args


def _decode_to_case(chunk):
    i = 0
    while True:
        m = re.search(r"\bDECODE\s*\(", chunk[i:], re.I)
        if not m:
            return chunk
        start = i + m.start()
        open_paren = i + m.end() - 1
        close = _find_close(chunk, open_paren)
        if close < 0:
            return chunk
        args = _split_top_args(chunk[open_paren + 1 : close])
        if len(args) >= 3:
            expr, rest = args[0], args[1:]
            default = rest.pop() if len(rest) % 2 == 1 else None
            whens = " ".join(f"WHEN {expr} = {rest[k]} THEN {rest[k+1]}" for k in range(0, len(rest), 2))
            rep = f"CASE {whens}{f' ELSE {default}' if default else ''} END"
        else:
            rep = chunk[start : close + 1]
        chunk = chunk[:start] + rep + chunk[close + 1 :]
        i = start + len(rep)


def _rownum_to_limit(stmt):
    if not re.search(r"\bSELECT\b", stmt, re.I) or re.search(r"\bLIMIT\s+\d+\b", stmt, re.I):
        return stmt
    limits = []

    def grab(m):
        op, num = m.group(1).strip(), int(m.group(2))
        limits.append(num - 1 if op == "<" else num)
        return ""

    stmt = re.sub(r"\bWHERE\s+ROWNUM\s*(<=|<|=)\s*(\d+)\b", grab, stmt, flags=re.I)
    stmt = re.sub(r"\bAND\s+ROWNUM\s*(<=|<|=)\s*(\d+)\b", grab, stmt, flags=re.I)
    stmt = re.sub(r"(?<![A-Za-z_])ROWNUM\s*(<=|<|=)\s*(\d+)\b", grab, stmt, flags=re.I)
    if limits:
        stmt = re.sub(r"\s{2,}", " ", stmt).strip().rstrip(";").strip()
        stmt = re.sub(r"\s+WHERE\s*$", "", stmt, flags=re.I)
        stmt = f"{stmt} LIMIT {min(limits)}"
    return stmt


def oracle_compat(sql):
    strs = []

    def stash(m):
        strs.append(m.group(0))
        return f"\x01{len(strs) - 1}\x01"

    masked = re.sub(r"'(?:[^']|'')*'", stash, sql)
    masked = _decode_to_case(masked)
    for pat, rep, fl in _ORACLE_RULES:
        masked = re.sub(pat, rep, masked, flags=fl)
    masked = _rownum_to_limit(masked)
    return re.sub(r"\x01(\d+)\x01", lambda m: strs[int(m.group(1))], masked)


def describe_table(name):
    if not IDENT_OK.match(name or ""):
        return None
    conn = get_conn()
    try:
        if USE_POSTGRES:
            cur = conn.execute(
                "SELECT column_name, is_nullable, data_type FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                [name.lower()],
            )
            raw = cur.fetchall()
            if not raw:
                return None
            pg_map = {
                "character varying": "VARCHAR",
                "numeric": "NUMBER",
                "integer": "NUMBER",
                "bigint": "NUMBER",
                "smallint": "NUMBER",
                "timestamp without time zone": "DATE",
                "timestamp with time zone": "TIMESTAMP",
                "text": "VARCHAR2",
                "boolean": "BOOLEAN",
            }
            out = []
            for cname, nullable, dtype in raw:
                t = next((o for p, o in pg_map.items() if dtype.startswith(p)), dtype.upper())
                out.append((cname.upper(), "" if nullable == "YES" else "NOT NULL", t))
            return out
        cur = conn.execute(f'PRAGMA table_info("{name}")')
        raw = cur.fetchall()
        if not raw:
            return None

        def orc_type(t):
            t = (t or "").upper().strip()
            if t.startswith("VARCHAR"):
                return "VARCHAR2" + t[len("VARCHAR"):]
            if t.startswith("NUMERIC"):
                return "NUMBER" + t[len("NUMERIC"):]
            if t.startswith("TIMESTAMP") or t.startswith("DATETIME"):
                return "DATE"
            if t.startswith("INT"):
                return "NUMBER"
            return t

        return [(r[1].upper(), "" if not r[3] else "NOT NULL", orc_type(r[2])) for r in raw]
    finally:
        conn.close()


def ensure_dual():
    try:
        conn = get_conn()
        try:
            if USE_POSTGRES:
                conn.execute("CREATE OR REPLACE VIEW dual AS SELECT 'X'::text AS dummy")
            else:
                conn.execute("CREATE VIEW IF NOT EXISTS dual AS SELECT 'X' AS dummy")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def list_tables():
    if USE_POSTGRES:
        sql = "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    else:
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    conn = get_conn()
    try:
        cur = conn.execute(sql)
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def table_counts():
    names = list_tables()
    out = []
    conn = get_conn()
    try:
        for n in names:
            cur = conn.execute(f'SELECT COUNT(*) FROM "{n}"')
            out.append({"name": n, "rows": cur.fetchone()[0]})
    finally:
        conn.close()
    return out


def table_data(name, limit=200):
    if not IDENT_OK.match(name or ""):
        raise ValueError(f"Invalid table name: {name!r}")
    conn = get_conn()
    try:
        cur = conn.execute(f'SELECT * FROM "{name}" LIMIT {int(limit)}')
        cols = [d[0] for d in cur.description]
        rows = [tuple(r) for r in cur.fetchall()]
        return {"name": name, "columns": cols, "rows": rows}
    finally:
        conn.close()


def drop_table(name):
    if not IDENT_OK.match(name or ""):
        raise ValueError(f"Invalid table name: {name!r}")
    conn = get_conn()
    try:
        conn.execute(f'DROP TABLE IF EXISTS "{name}"')
        conn.commit()
    finally:
        conn.close()


def clear_database():
    for n in list_tables():
        drop_table(n)
