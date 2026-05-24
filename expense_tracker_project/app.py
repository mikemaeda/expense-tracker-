from flask import Flask, render_template, request, redirect, url_for, session, make_response
import csv
import io
import os
import sqlite3
import smtplib
from datetime import datetime
from email.message import EmailMessage
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "expense_tracker.db")


def load_dotenv(dotenv_path):
    if not os.path.exists(dotenv_path):
        return
    with open(dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "expense_tracker_secret_key_2024")
app.jinja_env.globals["google_login_enabled"] = False

MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
MAIL_FROM = os.getenv("MAIL_FROM") or MAIL_USERNAME


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            description TEXT,
            expense_date TEXT NOT NULL,
            account_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            monthly_limit REAL NOT NULL,
            UNIQUE(account_id, category_id),
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        """
    )
    default_categories = [
        "Food",
        "Transportation",
        "Housing",
        "Utilities",
        "Entertainment",
        "Healthcare",
        "Education",
        "Shopping",
        "Other",
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO categories (category_name) VALUES (?)",
        [(category,) for category in default_categories],
    )
    connection.commit()
    connection.close()


def send_email(to_email, subject, body):
    if not MAIL_SERVER or not MAIL_USERNAME or not MAIL_PASSWORD or not MAIL_FROM:
        return False, "SMTP configuration is incomplete."

    try:
        message = EmailMessage()
        message["From"] = MAIL_FROM
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=15) as server:
            server.ehlo()
            if MAIL_USE_TLS:
                server.starttls()
                server.ehlo()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(message)
        return True, None
    except Exception as exc:
        app.logger.error("Email send failed: %s", exc)
        return False, str(exc)


def get_categories():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
    categories = cursor.fetchall()
    connection.close()
    return categories


def get_expense_for_account(expense_id, account_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, amount, description, expense_date, category_id, account_id
        FROM expenses
        WHERE id = ? AND account_id = ?
        """,
        (expense_id, account_id),
    )
    expense = cursor.fetchone()
    connection.close()
    return expense


def get_account_email(account_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT email FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    connection.close()
    return row["email"] if row else None


def get_monthly_category_total(account_id, category_id, expense_date):
    month_key = datetime.strptime(expense_date, "%Y-%m-%d").strftime("%Y-%m")
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE account_id = ? AND category_id = ? AND strftime('%Y-%m', expense_date) = ?
        """,
        (account_id, category_id, month_key),
    )
    total = cursor.fetchone()[0] or 0
    connection.close()
    return total


def notify_budget_if_needed(account_id, category_id, category_name, expense_date, new_total, monthly_limit):
    email = get_account_email(account_id)
    if not email or not monthly_limit:
        return

    if new_total >= monthly_limit:
        subject = f"Budget limit reached for {category_name}"
        body = f"You have spent ${new_total:.2f} of your ${monthly_limit:.2f} monthly {category_name} budget."
    elif new_total >= monthly_limit * 0.8:
        subject = f"Budget warning for {category_name}"
        body = f"You are close to your {category_name} budget: ${new_total:.2f} of ${monthly_limit:.2f}."
    else:
        return

    send_email(email, subject, body)


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "account_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


init_db()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_name = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        if not login_name or not password:
            return render_template("login.html", error="Please enter both username and password.")

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT id, password_hash FROM accounts WHERE login = ?", (login_name,))
        account = cursor.fetchone()
        connection.close()

        if not account:
            return render_template("login.html", error="Login not found. Please register first.")
        if not account["password_hash"] or not check_password_hash(account["password_hash"], password):
            return render_template("login.html", error="Invalid credentials.")

        session["account_id"] = account["id"]
        session["login"] = login_name
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        login_name = request.form.get("login", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not login_name or not email or not password:
            return render_template("register.html", error="Please provide username, email, and password.")
        if password != password_confirm:
            return render_template("register.html", error="Passwords do not match.", login=login_name, email=email)
        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters.", login=login_name, email=email)

        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO accounts (login, email, password_hash) VALUES (?, ?, ?)",
                (login_name, email, generate_password_hash(password)),
            )
            connection.commit()
            connection.close()
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username or email already exists.", login=login_name, email=email)

        email_sent, email_error = send_email(
            email,
            "Welcome to Expense Tracker",
            f"Hi {login_name},\n\nThanks for creating your Expense Tracker account.\n\n- Expense Tracker Team",
        )
        if not email_sent:
            app.logger.warning("Account created, but welcome email could not be sent: %s", email_error)

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/dashboard")
@login_required
def dashboard():
    category_filter = request.args.get("category", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    query = """
        SELECT expenses.id, amount, description, expense_date, category_name, categories.id
        FROM expenses
        JOIN categories ON expenses.category_id = categories.id
        WHERE account_id = ?
    """
    params = [session["account_id"]]

    if category_filter:
        query += " AND category_id = ?"
        params.append(category_filter)
    if start_date:
        query += " AND expense_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND expense_date <= ?"
        params.append(end_date)
    query += " ORDER BY expense_date DESC"

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(query, params)
    expenses = cursor.fetchall()

    total_query = "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE account_id = ?"
    total_params = [session["account_id"]]
    if category_filter:
        total_query += " AND category_id = ?"
        total_params.append(category_filter)
    if start_date:
        total_query += " AND expense_date >= ?"
        total_params.append(start_date)
    if end_date:
        total_query += " AND expense_date <= ?"
        total_params.append(end_date)
    cursor.execute(total_query, total_params)
    total = cursor.fetchone()[0] or 0

    cursor.execute(
        """
        SELECT categories.id, category_name, SUM(amount) as total
        FROM expenses
        JOIN categories ON expenses.category_id = categories.id
        WHERE account_id = ?
        GROUP BY categories.id, category_name
        ORDER BY total DESC
        """,
        (session["account_id"],),
    )
    category_stats = cursor.fetchall()

    cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
    categories = cursor.fetchall()

    cursor.execute(
        """
        SELECT budgets.id, categories.category_name, budgets.monthly_limit,
            COALESCE(SUM(expenses.amount), 0) as spent
        FROM budgets
        JOIN categories ON budgets.category_id = categories.id
        LEFT JOIN expenses ON expenses.category_id = budgets.category_id
            AND expenses.account_id = budgets.account_id
            AND strftime('%Y-%m', expenses.expense_date) = strftime('%Y-%m', 'now')
        WHERE budgets.account_id = ?
        GROUP BY budgets.id, categories.category_name, budgets.monthly_limit
        ORDER BY categories.category_name
        """,
        (session["account_id"],),
    )
    budget_stats = cursor.fetchall()
    connection.close()

    return render_template(
        "dashboard.html",
        expenses=expenses,
        total=round(total, 2),
        login=session["login"],
        categories=categories,
        category_stats=category_stats,
        monthly_stats=[],
        budget_stats=budget_stats,
        selected_category=category_filter,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_expense():
    categories = get_categories()
    if request.method == "POST":
        amount_raw = request.form.get("amount", "")
        description = request.form.get("description", "").strip()
        expense_date = request.form.get("expense_date", "").strip()
        category_id = request.form.get("category_id", "")

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return render_template("add_expense.html", categories=categories, error="Invalid amount. Please enter a positive number.")

        if not description or len(description) > 200:
            return render_template("add_expense.html", categories=categories, error="Description required (max 200 characters).")
        if not expense_date:
            return render_template("add_expense.html", categories=categories, error="Date is required.")
        try:
            datetime.strptime(expense_date, "%Y-%m-%d")
        except ValueError:
            return render_template("add_expense.html", categories=categories, error="Invalid date format. Use YYYY-MM-DD.")
        if not category_id:
            return render_template("add_expense.html", categories=categories, error="Please select a category.")

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO expenses (amount, description, expense_date, account_id, category_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (amount, description, expense_date, session["account_id"], category_id),
        )
        connection.commit()
        cursor.execute("SELECT category_name FROM categories WHERE id = ?", (category_id,))
        category_name = cursor.fetchone()["category_name"]
        cursor.execute("SELECT monthly_limit FROM budgets WHERE account_id = ? AND category_id = ?", (session["account_id"], category_id))
        budget = cursor.fetchone()
        connection.close()

        if budget:
            new_total = get_monthly_category_total(session["account_id"], int(category_id), expense_date)
            notify_budget_if_needed(session["account_id"], int(category_id), category_name, expense_date, new_total, budget["monthly_limit"])

        return redirect(url_for("dashboard"))

    return render_template("add_expense.html", categories=categories)


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    expense = get_expense_for_account(expense_id, session["account_id"])
    if not expense:
        return redirect(url_for("dashboard"))

    categories = get_categories()
    if request.method == "POST":
        amount_raw = request.form.get("amount", "")
        description = request.form.get("description", "").strip()
        expense_date = request.form.get("expense_date", "").strip()
        category_id = request.form.get("category_id", "")

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return render_template("edit_expense.html", expense=expense, categories=categories, error="Invalid amount.", expense_id=expense_id)
        if not description or len(description) > 200:
            return render_template("edit_expense.html", expense=expense, categories=categories, error="Description required (max 200 characters).", expense_id=expense_id)
        if not expense_date:
            return render_template("edit_expense.html", expense=expense, categories=categories, error="Date is required.", expense_id=expense_id)
        try:
            datetime.strptime(expense_date, "%Y-%m-%d")
        except ValueError:
            return render_template("edit_expense.html", expense=expense, categories=categories, error="Invalid date format. Use YYYY-MM-DD.", expense_id=expense_id)
        if not category_id:
            return render_template("edit_expense.html", expense=expense, categories=categories, error="Please select a category.", expense_id=expense_id)

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE expenses
            SET amount = ?, description = ?, expense_date = ?, category_id = ?
            WHERE id = ? AND account_id = ?
            """,
            (amount, description, expense_date, category_id, expense_id, session["account_id"]),
        )
        connection.commit()
        connection.close()
        return redirect(url_for("dashboard"))

    return render_template("edit_expense.html", expense=expense, categories=categories, expense_id=expense_id)


@app.route("/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ? AND account_id = ?", (expense_id, session["account_id"]))
    connection.commit()
    connection.close()
    return redirect(url_for("dashboard"))


@app.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    connection = get_connection()
    cursor = connection.cursor()

    if request.method == "POST":
        category_id = request.form.get("category_id", "")
        monthly_limit = request.form.get("monthly_limit", "")
        try:
            monthly_limit_value = float(monthly_limit)
            if not category_id or monthly_limit_value <= 0:
                raise ValueError
        except ValueError:
            connection.close()
            return render_template("budgets.html", categories=get_categories(), error="Enter a valid monthly budget.")

        cursor.execute(
            """
            INSERT INTO budgets (account_id, category_id, monthly_limit)
            VALUES (?, ?, ?)
            ON CONFLICT(account_id, category_id) DO UPDATE SET monthly_limit = excluded.monthly_limit
            """,
            (session["account_id"], category_id, monthly_limit_value),
        )
        connection.commit()

    cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
    categories = cursor.fetchall()
    cursor.execute(
        """
        SELECT budgets.id, budgets.category_id, categories.category_name, budgets.monthly_limit,
            COALESCE(SUM(expenses.amount), 0) as spent
        FROM budgets
        JOIN categories ON budgets.category_id = categories.id
        LEFT JOIN expenses ON expenses.category_id = budgets.category_id
            AND expenses.account_id = budgets.account_id
            AND strftime('%Y-%m', expenses.expense_date) = strftime('%Y-%m', 'now')
        WHERE budgets.account_id = ?
        GROUP BY budgets.id, budgets.category_id, categories.category_name, budgets.monthly_limit
        ORDER BY categories.category_name
        """,
        (session["account_id"],),
    )
    saved_budgets = cursor.fetchall()
    connection.close()
    return render_template("budgets.html", categories=categories, budgets=saved_budgets)


@app.route("/export.csv")
@login_required
def export_csv():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT amount, description, expense_date, category_name
        FROM expenses
        JOIN categories ON expenses.category_id = categories.id
        WHERE account_id = ?
        ORDER BY expense_date DESC
        """,
        (session["account_id"],),
    )
    rows = cursor.fetchall()
    connection.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["amount", "description", "expense_date", "category"])
    for row in rows:
        writer.writerow([row["amount"], row["description"], row["expense_date"], row["category_name"]])

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
    return response


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
