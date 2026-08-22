import base64
import os

from flask import Flask, render_template, request

import db
import lessons

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

db.ensure_dual()


def _decode_incoming(sql):
    """Accept optional 'B64:' prefix so WAFs don't flag legitimate SQL keywords."""
    sql = (sql or "").strip()
    if sql.startswith("B64:"):
        try:
            return base64.b64decode(sql[4:]).decode("utf-8", "replace").strip()
        except Exception:
            return ""
    return sql


@app.route("/", methods=["GET", "POST"])
def console():
    results = None
    submitted = ""
    if request.method == "POST":
        submitted = _decode_incoming(request.form.get("sql", ""))
        if submitted:
            results = db.run_sql(submitted)
    else:
        submitted = _decode_incoming(request.args.get("sql", ""))
    if db.USE_POSTGRES:
        tables_sql = "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
    else:
        tables_sql = "SELECT name FROM sqlite_master WHERE type = 'table';"
    return render_template("index.html", results=results, submitted=submitted, tables_sql=tables_sql)


@app.route("/workout")
def workout():
    return render_template("workout.html", lessons=lessons.LESSONS,
                           levels=lessons.LEVELS, setup_sql=lessons.SETUP_SQL)


@app.route("/database")
def database():
    tables = db.table_counts()
    selected = request.args.get("table", "").strip()
    data = None
    error = None
    if selected:
        try:
            data = db.table_data(selected)
        except Exception as exc:
            error = str(exc)
    return render_template("database.html", tables=tables, data=data, error=error)


@app.route("/api/version")
def api_version():
    return {"commit": os.environ.get("RENDER_GIT_COMMIT", "local")[:7],
            "postgres": db.USE_POSTGRES}


@app.route("/api/dbg")
def api_dbg():
    q = request.args.get("q", "")
    return {"raw": q, "translated": db.oracle_compat(q), "tables": db.list_tables()}


@app.route("/api/tables")
def api_tables():
    return {"tables": db.list_tables()}


@app.route("/api/table_counts")
def api_table_counts():
    return {"tables": db.table_counts()}


@app.route("/api/drop_table", methods=["POST"])
def api_drop_table():
    name = (request.get_json(silent=True) or {}).get("name", "")
    try:
        db.drop_table(name)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}, 400


@app.route("/api/clear_database", methods=["POST"])
def api_clear_database():
    try:
        db.clear_database()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}, 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
