import os

from flask import Flask, render_template, request

import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

db.ensure_dual()


@app.route("/", methods=["GET", "POST"])
def console():
    results = None
    submitted = ""
    if request.method == "POST":
        submitted = request.form.get("sql", "").strip()
        if submitted:
            results = db.run_sql(submitted)
    if db.USE_POSTGRES:
        tables_sql = "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
    else:
        tables_sql = "SELECT name FROM sqlite_master WHERE type = 'table';"
    return render_template("index.html", results=results, submitted=submitted, tables_sql=tables_sql)


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
