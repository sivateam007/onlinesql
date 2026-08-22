SETUP_SQL = """DROP TABLE IF EXISTS emp;
DROP TABLE IF EXISTS dept;
CREATE TABLE dept (dno NUMBER(2), dname VARCHAR2(20));
CREATE TABLE emp (eno NUMBER(4), ename VARCHAR2(20), sal NUMBER(8,2), dno NUMBER(2));
INSERT INTO dept VALUES (10, 'SALES');
INSERT INTO dept VALUES (20, 'IT');
INSERT INTO dept VALUES (30, 'HR');
INSERT INTO emp VALUES (101, 'siva', 50000, 20);
INSERT INTO emp VALUES (102, 'arun', 42000, 10);
INSERT INTO emp VALUES (103, 'priya', 60000, 20);
INSERT INTO emp VALUES (104, 'ravi', 35000, 30);
INSERT INTO emp VALUES (105, 'meena', 75000, 10);
INSERT INTO emp VALUES (106, 'kiran', 28000, 30);"""

LEVELS = {
    1: {"name": "BASE", "icon": "fa-seedling", "color": "#16a34a",
        "desc": "Foundation week — read, filter, sort and change data."},
    2: {"name": "MEDIUM", "icon": "fa-dumbbell", "color": "#ea580c",
        "desc": "Patterns, grouping, joins and subqueries."},
}

LESSONS = [
    # ---------- LEVEL 1 : BASE ----------
    dict(id="b1", level=1, day=1, title="SELECT — read your data",
         learn="SELECT picks columns FROM a table. * means every column.",
         example="SELECT * FROM emp;\nSELECT ename, sal FROM emp;",
         task="Show only ename and sal of every employee.",
         solution="SELECT ename, sal FROM emp;"),
    dict(id="b2", level=1, day=2, title="WHERE — filter rows",
         learn="WHERE keeps only rows that match a condition.",
         example="SELECT * FROM emp WHERE sal > 40000;\nSELECT * FROM emp WHERE dno = 20;",
         task="Show employees who earn more than 50000.",
         solution="SELECT * FROM emp WHERE sal > 50000;"),
    dict(id="b3", level=1, day=3, title="AND / OR — combine conditions",
         learn="AND = both must be true. OR = at least one true.",
         example="SELECT * FROM emp WHERE sal > 30000 AND dno = 30;\nSELECT * FROM emp WHERE dno = 10 OR dno = 20;",
         task="Employees in department 30 earning above 25000.",
         solution="SELECT * FROM emp WHERE dno = 30 AND sal > 25000;"),
    dict(id="b4", level=1, day=4, title="ORDER BY — sorting",
         learn="ORDER BY sorts: ASC low→high (default), DESC high→low.",
         example="SELECT * FROM emp ORDER BY sal;\nSELECT * FROM emp ORDER BY sal DESC;",
         task="Show names sorted by salary, highest first.",
         solution="SELECT ename, sal FROM emp ORDER BY sal DESC;"),
    dict(id="b5", level=1, day=5, title="INSERT — add rows",
         learn="INSERT adds a new row. Column order must match VALUES order.",
         example="INSERT INTO emp VALUES (107, 'divya', 55000, 20);",
         task="Add employee 108, name 'gopal', salary 31000, dept 10.",
         solution="INSERT INTO emp VALUES (108, 'gopal', 31000, 10);\nSELECT * FROM emp;"),
    dict(id="b6", level=1, day=6, title="UPDATE & DELETE — careful!",
         learn="UPDATE changes rows, DELETE removes them. ALWAYS use WHERE — no WHERE means EVERY row!",
         example="UPDATE emp SET sal = sal + 5000 WHERE eno = 104;\nDELETE FROM emp WHERE eno = 106;",
         task="Give kiran a 2000 raise, then delete him.",
         solution="UPDATE emp SET sal = sal + 2000 WHERE ename = 'kiran';\nDELETE FROM emp WHERE ename = 'kiran';\nSELECT * FROM emp;"),
    dict(id="b7", level=1, day=7, title="COUNT & DISTINCT — mini project",
         learn="COUNT(*) counts rows. DISTINCT removes duplicates from results.",
         example="SELECT COUNT(*) FROM emp;\nSELECT DISTINCT dno FROM emp;",
         task="How many employees earn under 50000? How many different departments exist?",
         solution="SELECT COUNT(*) AS under50k FROM emp WHERE sal < 50000;\nSELECT COUNT(DISTINCT dno) AS depts FROM emp;"),

    # ---------- LEVEL 2 : MEDIUM ----------
    dict(id="m1", level=2, day=8, title="LIKE — pattern search",
         learn="% matches any text, _ matches one character. Names starting with s → 's%'.",
         example="SELECT * FROM emp WHERE ename LIKE 's%';\nSELECT * FROM emp WHERE ename LIKE '%a%';",
         task="Find employees whose name ends with 'a'.",
         solution="SELECT * FROM emp WHERE ename LIKE '%a';"),
    dict(id="m2", level=2, day=9, title="IN / BETWEEN — range filters",
         learn="IN checks a list of values. BETWEEN is inclusive on both sides.",
         example="SELECT * FROM emp WHERE dno IN (10, 30);\nSELECT * FROM emp WHERE sal BETWEEN 35000 AND 60000;",
         task="Salaries between 40000 and 70000 in departments 10 or 20.",
         solution="SELECT * FROM emp WHERE sal BETWEEN 40000 AND 70000 AND dno IN (10, 20);"),
    dict(id="m3", level=2, day=10, title="GROUP BY — summarize",
         learn="GROUP BY collapses rows per group so SUM/AVG/COUNT/MAX/MIN can work on each group.",
         example="SELECT dno, SUM(sal) FROM emp GROUP BY dno;\nSELECT dno, AVG(sal), COUNT(*) FROM emp GROUP BY dno;",
         task="Average salary per department.",
         solution="SELECT dno, AVG(sal) AS avg_sal FROM emp GROUP BY dno;"),
    dict(id="m4", level=2, day=11, title="HAVING — filter groups",
         learn="WHERE filters rows BEFORE grouping; HAVING filters groups AFTER.",
         example="SELECT dno, COUNT(*) FROM emp GROUP BY dno HAVING COUNT(*) > 1;",
         task="Departments whose total salary bill is above 90000.",
         solution="SELECT dno, SUM(sal) AS total FROM emp GROUP BY dno HAVING SUM(sal) > 90000;"),
    dict(id="m5", level=2, day=12, title="JOIN — combine tables",
         learn="JOIN matches rows of two tables using a common column (emp.dno ↔ dept.dno).",
         example="SELECT e.ename, d.dname\nFROM emp e JOIN dept d ON e.dno = d.dno;",
         task="Show each employee name with their department NAME.",
         solution="SELECT e.ename, d.dname FROM emp e JOIN dept d ON e.dno = d.dno ORDER BY e.ename;"),
    dict(id="m6", level=2, day=13, title="Subqueries — query inside query",
         learn="A SELECT inside another SELECT. Useful when the answer needs two steps.",
         example="SELECT * FROM emp WHERE sal > (SELECT AVG(sal) FROM emp);",
         task="Who earns more than the company average?",
         solution="SELECT ename, sal FROM emp WHERE sal > (SELECT AVG(sal) FROM emp) ORDER BY sal DESC;"),
    dict(id="m7", level=2, day=14, title="Constraints + final challenge",
         learn="PRIMARY KEY makes a column unique + required. NOT NULL forbids empty. UNIQUE forbids duplicates.",
         example="CREATE TABLE team (\n  tid NUMBER(3) PRIMARY KEY,\n  tname VARCHAR2(15) NOT NULL UNIQUE\n);",
         task="Create table players (pid NUMBER(3) PRIMARY KEY, pname VARCHAR2(15) NOT NULL, runs NUMBER(5)) and insert 2 rows.",
         solution="CREATE TABLE players (pid NUMBER(3) PRIMARY KEY,\n  pname VARCHAR2(15) NOT NULL, runs NUMBER(5));\nINSERT INTO players VALUES (1, 'virat', 12000);\nINSERT INTO players VALUES (2, 'rohit', 9800);\nSELECT * FROM players;"),
]
