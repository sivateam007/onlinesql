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
                cur = conn.execute(stmt)
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
