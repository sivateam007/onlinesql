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
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


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


def _error_hint(err_text):
    t = err_text.lower()
    if ("no such table" in t) or ("does not exist" in t and "column" not in t):
        try:
            avail = ", ".join(list_tables())
        except Exception:
            avail = ""
        if avail:
            return f"That table doesn't exist yet. Available tables: {avail}. Check spelling, or CREATE it first."
        return "There are no tables yet — create one first, e.g. CREATE TABLE students (id NUMBER(3), name VARCHAR2(20));"
    if "no such column" in t or ("column" in t and "does not exist" in t):
        return "Column name problem — run DESC tablename to see the exact column names."
    if "syntax error" in t or "incomplete input" in t:
        if "modify" in t:
            return "Changing a column type (ALTER ... MODIFY) works on the cloud database — the local demo engine doesn't support it."
        return "Check spelling, commas, quotes and closing brackets. End each statement with ;"
    if "unique constraint" in t or "primary key" in t or "unique constraint failed" in t:
        return "That value already exists and must stay unique (PRIMARY KEY / UNIQUE rule)."
    if "check constraint" in t or "violates check" in t:
        return "That value breaks a CHECK rule defined on this column (e.g. age >= 18)."
    if "foreign key constraint" in t or "violates foreign key" in t:
        return "Foreign key violation — the referenced parent row doesn't exist. Insert the parent table row first."
    if "already exists" in t:
        return "An object with this name already exists. Use a new name or DROP the old one first."
    return None


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
            m_orv = re.match(
                r"\s*CREATE\s+OR\s+REPLACE\s+VIEW\s+([A-Za-z_]\w*)\s+AS\s+(.+)",
                stmt,
                re.I | re.S,
            )
            try:
                if m_orv and not USE_POSTGRES:
                    conn.execute(f"DROP VIEW IF EXISTS {m_orv.group(1)}")
                    translated = f"CREATE VIEW {m_orv.group(1)} AS {m_orv.group(2)}"
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
                h = _error_hint(entry["text"])
                if h:
                    entry["hint"] = h
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
        lambda m: f"STRING_AGG({m.group(1)} ORDER BY {m.group(2)})",
        re.I,
    ),
    (
        r"\bTO_CHAR\s*\(\s*([^,()]+?)\s*\)",
        r"CAST(\1 AS TEXT)",
        re.I,
    ),
    (
        r"\bINSTR\s*\(\s*([^,()]+?)\s*,\s*([^,()]+?)\s*\)",
        lambda m: f"POSITION({m.group(2)} IN {m.group(1)})",
        re.I,
    ),
]

_MODIFY_RULE = (
    r"\bMODIFY\s+([A-Za-z_]\w*)\s+(NUMERIC(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?|VARCHAR\s*\(\s*\d+\s*\)|TIMESTAMP)\s*$",
    r"ALTER COLUMN \1 TYPE \2",
    re.I,
)

_PG_ONLY_RULES = [
    (
        r"\bADD_MONTHS\s*\(\s*([^,()]+?)\s*,\s*([^,()]+?)\s*\)",
        lambda m: f"(({m.group(1)}) + INTERVAL '1 month' * ({m.group(2)}))",
        re.I,
    ),
    (
        r"\bLAST_DAY\s*\(\s*([^,()]+?)\s*\)",
        lambda m: f"(date_trunc('month', ({m.group(1)})) + INTERVAL '1 month - 1 day')",
        re.I,
    ),
    (
        r"\bMONTHS_BETWEEN\s*\(\s*([^,()]+?)\s*,\s*([^,()]+?)\s*\)",
        lambda m: f"((EXTRACT(YEAR FROM AGE(({m.group(1)}), ({m.group(2)}))) * 12 + EXTRACT(MONTH FROM AGE(({m.group(1)}), ({m.group(2)})))))",
        re.I,
    ),
    (
        r"\b([A-Za-z_]\w*)\s*\.\s*NEXTVAL\b",
        lambda m: f"nextval('{m.group(1)}')",
        re.I,
    ),
    (
        r"\b([A-Za-z_]\w*)\s*\.\s*CURRVAL\b",
        lambda m: f"currval('{m.group(1)}')",
        re.I,
    ),
    (r"\bSYSTIMESTAMP\b", "CURRENT_TIMESTAMP", re.I),
    (
        r"\bTRUNC\s*\(\s*(?:SYSDATE|CURRENT_TIMESTAMP)\s*\)",
        "date_trunc('day', CURRENT_TIMESTAMP)",
        re.I,
    ),
    (
        r"\bBITAND\s*\(\s*([^,()]+?)\s*,\s*([^,()]+?)\s*\)",
        lambda m: f"(({m.group(1)}) & ({m.group(2)}))",
        re.I,
    ),
    (
        r"\bMEDIAN\s*\(\s*([^()]+?)\s*\)",
        lambda m: f"percentile_cont(0.5) WITHIN GROUP (ORDER BY {m.group(1)})",
        re.I,
    ),
    (
        r"\bREGEXP_LIKE\s*\(\s*([^,]+?),\s*([^)]+?)\s*\)",
        lambda m: f"({m.group(1)} ~ {m.group(2)})",
        re.I,
    ),
    (
        r"\bNEXT_DAY\s*\(\s*([^,()]+?)\s*,\s*([^,()]+?)\s*\)",
        lambda m: (
            f"(({m.group(1)}) + INTERVAL '1 day' * "
            f"((((CASE upper({m.group(2)}) WHEN 'SUNDAY' THEN 0 WHEN 'MONDAY' THEN 1 "
            f"WHEN 'TUESDAY' THEN 2 WHEN 'WEDNESDAY' THEN 3 WHEN 'THURSDAY' THEN 4 "
            f"WHEN 'FRIDAY' THEN 5 WHEN 'SATURDAY' THEN 6 END)::int "
            f"- EXTRACT(DOW FROM ({m.group(1)}))::int + 6) % 7) + 1))"
        ),
        re.I,
    ),
]


def _rules_for(pg):
    rules = list(_ORACLE_RULES)
    if pg:
        rules += [_MODIFY_RULE] + _PG_ONLY_RULES
    return rules


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


def _nvl2_to_case(chunk):
    i = 0
    while True:
        m = re.search(r"\bNVL2\s*\(", chunk[i:], re.I)
        if not m:
            return chunk
        start = i + m.start()
        open_paren = i + m.end() - 1
        close = _find_close(chunk, open_paren)
        if close < 0:
            return chunk
        args = _split_top_args(chunk[open_paren + 1 : close])
        if len(args) == 3:
            rep = f"CASE WHEN {args[0]} IS NOT NULL THEN {args[1]} ELSE {args[2]} END"
        else:
            rep = chunk[start : close + 1]
        chunk = chunk[:start] + rep + chunk[close + 1 :]
        i = start + len(rep)


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


def oracle_compat(sql, pg=None):
    if pg is None:
        pg = USE_POSTGRES
    rules = _rules_for(pg)
    strs = []

    def stash(m):
        strs.append(m.group(0))
        return f"\x01{len(strs) - 1}\x01"

    masked = re.sub(r"'(?:[^']|'')*'", stash, sql)
    masked = _decode_to_case(masked)
    masked = _nvl2_to_case(masked)
    for pat, rep, fl in rules:
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
                "SELECT column_name, is_nullable, data_type, character_maximum_length, "
                "numeric_precision, numeric_scale FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                [name.lower()],
            )
            raw = cur.fetchall()
            if not raw:
                return None
            out = []
            for cname, nullable, dtype, clen, nprec, nscale in raw:
                if dtype.startswith("character varying"):
                    t = f"VARCHAR2({clen})" if clen else "VARCHAR2"
                elif dtype == "numeric":
                    t = f"NUMBER({nprec},{nscale})" if nscale else (f"NUMBER({nprec})" if nprec else "NUMBER")
                elif dtype.startswith("timestamp"):
                    t = "DATE"
                elif dtype in ("integer", "bigint", "smallint"):
                    t = "NUMBER"
                elif dtype == "text":
                    t = "VARCHAR2"
                elif dtype == "boolean":
                    t = "BOOLEAN"
                else:
                    t = dtype.upper()
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
