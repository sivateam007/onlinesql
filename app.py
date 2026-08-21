import os

from flask import Flask, flash, redirect, render_template, request, url_for

import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

db.init_db()


@app.route("/", methods=["GET", "POST"])
def console():
    results = None
    submitted = ""
    if request.method == "POST":
        submitted = request.form.get("sql", "").strip()
        if submitted:
            results = db.run_sql(submitted)
    if db.USE_POSTGRES:
        backend = "PostgreSQL"
        tables_sql = "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
    else:
        backend = "SQLite (local demo)"
        tables_sql = "SELECT name FROM sqlite_master WHERE type = 'table';"
    return render_template(
        "index.html",
        results=results,
        submitted=submitted,
        backend=backend,
        tables_sql=tables_sql,
    )


@app.route("/api/tables")
def api_tables():
    return {"tables": db.list_tables()}


@app.route("/students")
def students():
    rows = db.fetch_all()
    return render_template("students.html", students=rows)


@app.route("/add", methods=["POST"])
def add():
    sid = request.form.get("sid", "").strip()
    name = request.form.get("name", "").strip()
    mobile = request.form.get("mobile", "").strip()

    if not sid or not name:
        flash("SID and Name are required!")
        return redirect(url_for("students"))

    try:
        db.add_student(int(sid), name, mobile)
        flash(f"SQL executed: INSERT INTO students VALUES ({sid}, '{name}', '{mobile}') — 1 row created ✅")
    except Exception as exc:
        flash(f"Database error: {exc.__class__.__name__} — maybe that SID already exists? (PRIMARY KEY guard 👮)")
    return redirect(url_for("students"))


@app.route("/delete", methods=["POST"])
def delete():
    sid = request.form.get("sid", "").strip()
    if sid:
        removed = db.delete_student(int(sid))
        if removed:
            flash(f"SQL executed: DELETE FROM students WHERE sid = {sid} — 1 row deleted 🗑️")
        else:
            flash(f"DELETE FROM students WHERE sid = {sid} — no rows matched!")
    return redirect(url_for("students"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
