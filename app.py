import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session

try:
    from config import SECRET_KEY, APP_PASSWORD
except ImportError:
    raise RuntimeError("Создай файл config.py с SECRET_KEY и APP_PASSWORD")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(days=30)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "expenses.db")
CATEGORIES = ["Еда", "Транспорт", "Развлечения", "Учёба", "Другое"]


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            comment TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        entered = request.form["password"].encode("utf-8")
        correct = APP_PASSWORD.encode("utf-8")
        if secrets.compare_digest(entered, correct):
            session["logged_in"] = True
            session.permanent = True
            return redirect(url_for("home"))
        error = "Неверный пароль"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    conn = get_db()
    expenses = conn.execute(
        "SELECT * FROM expenses ORDER BY date DESC, id DESC"
    ).fetchall()
    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses"
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "GROUP BY category ORDER BY total DESC"
    ).fetchall()

    now = datetime.now()
    month_key = now.strftime("%Y-%m")
    month_spent = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE substr(date, 1, 7) = ?",
        (month_key,),
    ).fetchone()[0]

    row = conn.execute("SELECT value FROM settings WHERE key = 'budget'").fetchone()
    budget = float(row["value"]) if row else 0
    conn.close()

    labels = [r["category"] for r in rows]
    values = [r["total"] for r in rows]
    percent = min(100, month_spent / budget * 100) if budget > 0 else 0

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        labels=labels,
        values=values,
        budget=budget,
        month_spent=month_spent,
        remaining=budget - month_spent,
        percent=percent,
        month_label=now.strftime("%m.%Y"),
    )


@app.route("/add", methods=["POST"])
@login_required
def add():
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (date, category, amount, comment) VALUES (?, ?, ?, ?)",
        (
            request.form["date"],
            request.form["category"],
            float(request.form["amount"]),
            request.form["comment"],
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home"))


@app.route("/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete(expense_id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit(expense_id):
    conn = get_db()

    if request.method == "POST":
        conn.execute(
            "UPDATE expenses SET date = ?, category = ?, amount = ?, comment = ? WHERE id = ?",
            (
                request.form["date"],
                request.form["category"],
                float(request.form["amount"]),
                request.form["comment"],
                expense_id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("home"))

    expense = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()

    if expense is None:
        return redirect(url_for("home"))

    return render_template("edit.html", expense=expense, categories=CATEGORIES)


@app.route("/budget", methods=["POST"])
@login_required
def set_budget():
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('budget', ?)",
        (str(float(request.form["budget"])),),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)