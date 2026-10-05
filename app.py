from datetime import datetime

import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
DB_NAME = "expenses.db"
CATEGORIES = ["Еда", "Транспорт", "Развлечения", "Учёба", "Другое"]

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
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
def set_budget():
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('budget', ?)",
        (str(float(request.form["budget"])),),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

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


@app.route("/")
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


init_db()

if __name__ == "__main__":
    app.run(debug=True)