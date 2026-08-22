# SIVA — Online SQL Console

Practice real SQL online. Write queries in your browser, run them against a real database, and see results instantly — from your phone or laptop.

**Live app:** https://onlinesql.onrender.com

## Pages

| Page | What it does |
|---|---|
| **SQL Console** (`/`) | Run any SQL — CREATE, INSERT, SELECT, UPDATE, DELETE, COMMIT, ROLLBACK. Multi-statement scripts supported (end each line with `;`). |
| **Daily Workout** (`/workout`) | A 14-day guided course: Level 1 BASE (Days 1–7) and Level 2 MEDIUM (Days 8–14), one topic per day with tasks, solutions and progress tracking. |
| **Database Manager** (`/database`) | Browse all tables, view rows visually (up to 200 per table), drop single tables or clear the whole database. |

## Features

- Multi-statement execution with per-statement status ("N rows affected.")
- Result grids for SELECT queries
- Available-tables chips — click to insert `SELECT * FROM tablename;`
- Smart error hints (missing table, wrong column, syntax problems, duplicate keys…)
- Query history saved in your browser (last 30 commands)
- Danger zone with confirmation dialogs before destructive actions

## Oracle Compatibility

Type Oracle-style SQL and it just works:

- Types: `NUMBER(p,s)`, `VARCHAR2(n)`, `DATE`
- Functions: `SYSDATE`, `NVL`, `DECODE`, `LISTAGG(...) WITHIN GROUP (...)`
- `FROM dual` (a `dual` view is created automatically)
- `WHERE ROWNUM <= n` (translated to `LIMIT`)
- `DESC tablename` / `DESCRIBE tablename` (Oracle-style column listing)
- `MINUS` (translated to `EXCEPT`)
- SQL*Plus formatting commands (`SET LINESIZE ...` etc.) are silently ignored

Not supported: PL/SQL blocks (`DECLARE/BEGIN ... END`) — plain SQL only.

## Tech Stack

- **Backend:** Python + Flask
- **Database:** PostgreSQL (Render free tier); falls back to SQLite when running locally without `DATABASE_URL`
- **Deployment:** Render Blueprint (`render.yaml`) — web service + database, auto-deploys on push to `main`

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 — it will use SQLite automatically.

## Project Structure

```
app.py          Flask routes (console, workout, database manager, JSON APIs)
db.py           Database engine + Oracle-compatibility translator
lessons.py      Daily Workout curriculum data
templates/      index.html, workout.html, database.html
static/style.css
render.yaml     Render deployment config
requirements.txt
```
