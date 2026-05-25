from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response
import sqlite3
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
import csv
import io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = bool(os.getenv("VERCEL"))
DEFAULT_DATABASE_PATH = (
    os.path.join("/tmp", "expense_tracker.db")
    if IS_VERCEL
    else os.path.join(BASE_DIR, "expense_tracker.db")
)

def load_dotenv(dotenv_path):
    if not os.path.exists(dotenv_path):
        return
    with open(dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    if IS_VERCEL:
        raise RuntimeError("FLASK_SECRET_KEY must be set in Vercel environment variables.")
    app.secret_key = "expense_tracker_dev_secret_key"

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_VERCEL,
)

MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
MAIL_FROM = os.getenv("MAIL_FROM") or MAIL_USERNAME
PLACEHOLDER_CONFIG_VALUES = {
    "",
    "your@gmail.com",
    "your_app_password",
    "your_google_client_id",
    "your_google_client_secret",
    "super-secret-key",
}


def is_configured_value(value):
    return bool(value and value.strip() and value.strip() not in PLACEHOLDER_CONFIG_VALUES)

if not IS_VERCEL:
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_LOGIN_ENABLED = is_configured_value(GOOGLE_CLIENT_ID) and is_configured_value(GOOGLE_CLIENT_SECRET)

oauth = OAuth(app)
if GOOGLE_LOGIN_ENABLED:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        access_token_url="https://oauth2.googleapis.com/token",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        api_base_url="https://openidconnect.googleapis.com/v1/",
        client_kwargs={"scope": "openid email profile"},
    )

app.jinja_env.globals["google_login_enabled"] = GOOGLE_LOGIN_ENABLED


def send_email(to_email, subject, body):
    if not all(is_configured_value(value) for value in (MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD, MAIL_FROM)):
        return False, "SMTP configuration is incomplete. Please set MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD and MAIL_FROM."

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

        app.logger.info("Email sent to %s via %s", to_email, MAIL_SERVER)
        return True, None
    except Exception as exc:
        error_message = str(exc)
        app.logger.error("Email send failed: %s", error_message)
        return False, error_message


def get_account_email(account_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT email FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    connection.close()
    return row["email"] if row else None


def get_account_by_email(email):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, login FROM accounts WHERE email = ?", (email,))
    row = cursor.fetchone()
    connection.close()
    return row


def create_google_account(email):
    connection = get_connection()
    cursor = connection.cursor()
    base_login = email.split("@")[0]
    candidate_login = base_login
    suffix = 1
    while cursor.execute("SELECT 1 FROM accounts WHERE login = ?", (candidate_login,)).fetchone():
        candidate_login = f"{base_login}{suffix}"
        suffix += 1

    cursor.execute(
        "INSERT INTO accounts (login, email) VALUES (?, ?)",
        (candidate_login, email),
    )
    connection.commit()
    account_id = cursor.lastrowid
    connection.close()
    return account_id, candidate_login


def get_monthly_category_total(account_id, category_id, expense_date, exclude_id=None):
    month_key = datetime.strptime(expense_date, "%Y-%m-%d").strftime("%Y-%m")
    connection = get_connection()
    cursor = connection.cursor()
    query = "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE account_id = ? AND category_id = ? AND strftime('%Y-%m', expense_date) = ?"
    params = [account_id, category_id, month_key]
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
    cursor.execute(query, params)
    total = cursor.fetchone()[0] or 0
    connection.close()
    return total


def notify_budget_if_needed(account_id, category_id, category_name, expense_date, new_total, monthly_limit):
    if not monthly_limit:
        return

    email = get_account_email(account_id)
    if not email:
        return

    threshold = monthly_limit * 0.8
    if new_total >= monthly_limit:
        subject = f"Budget limit reached for {category_name}"
        body = (
            f"You have reached your monthly budget limit for {category_name}.\n"
            f"This month you have spent ${new_total:.2f} and your limit is ${monthly_limit:.2f}."
        )
    elif new_total >= threshold:
        subject = f"Budget warning for {category_name}"
        body = (
            f"You are close to your monthly budget limit for {category_name}.\n"
            f"This month you have spent ${new_total:.2f} of ${monthly_limit:.2f}."
        )
    else:
        return

    send_email(email, subject, body)

def get_connection():
    database_path = os.getenv("DATABASE_PATH", DEFAULT_DATABASE_PATH)
    database_dir = os.path.dirname(database_path)
    if database_dir:
        os.makedirs(database_dir, exist_ok=True)

    conn = sqlite3.connect(database_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


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

    cursor.execute("PRAGMA table_info(accounts)")
    account_columns = {row["name"] for row in cursor.fetchall()}
    if "email" not in account_columns:
        cursor.execute("ALTER TABLE accounts ADD COLUMN email TEXT")
    if "password_hash" not in account_columns:
        cursor.execute("ALTER TABLE accounts ADD COLUMN password_hash TEXT")

    try:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_email_unique ON accounts(email) WHERE email IS NOT NULL"
        )
    except sqlite3.IntegrityError:
        app.logger.warning("Skipping unique email index because duplicate account emails already exist.")

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


init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "account_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_name = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        if not login_name or not password:
            return render_template("login.html", error="Please enter both username and password.")

        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id, password_hash FROM accounts WHERE login = ?", (login_name,))
            account = cursor.fetchone()

            if not account:
                connection.close()
                return render_template("login.html", error="Login not found. Please register first.")

            stored_hash = account["password_hash"] if "password_hash" in account.keys() else None
            if not stored_hash:
                connection.close()
                return render_template("login.html", error="Account has no password set. Please register a new account.")

            if check_password_hash(stored_hash, password):
                session["account_id"] = account["id"]
                session["login"] = login_name
                connection.close()
                return redirect(url_for("dashboard"))
            else:
                connection.close()
                return render_template("login.html", error="Invalid credentials.")
        except Exception as exc:
            app.logger.exception("Login failed")
            return render_template("login.html", error=f"Login error: {exc}")

    return render_template("login.html")


@app.route("/login/google")
def login_google():
    if not GOOGLE_LOGIN_ENABLED:
        return render_template("login.html", error="Google login is not configured on this server.")
    redirect_uri = url_for("google_auth_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/login/google/callback")
def google_auth_callback():
    if not GOOGLE_LOGIN_ENABLED:
        return render_template("login.html", error="Google login is not configured on this server.")

    try:
        token = oauth.google.authorize_access_token()
        user_info = oauth.google.get("userinfo").json()
        email = user_info.get("email")

        if not email:
            raise ValueError("Google did not provide an email address.")

        account = get_account_by_email(email)
        if account:
            account_id = account["id"]
            login_name = account["login"]
            created = False
        else:
            account_id, login_name = create_google_account(email)
            created = True

        session["account_id"] = account_id
        session["login"] = login_name

        if created:
            subject = "Welcome to Expense Tracker"
            body = (
                f"Hi {login_name},\n\n"
                "Thanks for signing in with Google. "
                "You can now start tracking your spending, set budgets, and get alerts when you approach your limits.\n\n"
                "If you did not authorize this account, please contact us immediately.\n\n"
                "- Expense Tracker Team"
            )
            send_email(email, subject, body)

        return redirect(url_for("dashboard"))
    except Exception as exc:
        app.logger.exception("Google login failed")
        return render_template("login.html", error=f"Google login error: {exc}")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        login_name = request.form.get("login", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        email = request.form.get("email", "").strip()

        if not login_name or not password or not email:
            return render_template("register.html", error="Please provide username, email, and password.")
        if password != password_confirm:
            return render_template("register.html", error="Passwords do not match.")
        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters.")

        try:
            connection = get_connection()
            cursor = connection.cursor()
            pwd_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO accounts (login, password_hash, email) VALUES (?, ?, ?)",
                (login_name, pwd_hash, email)
            )
            connection.commit()
            connection.close()

            subject = "Welcome to Expense Tracker"
            body = (
                f"Hi {login_name},\n\n"
                "Thanks for creating your Expense Tracker account. "
                "You can now start tracking your spending, set budgets, and get alerts when you approach your limits.\n\n"
                "If you did not create this account, please contact us immediately.\n\n"
                "- Expense Tracker Team"
            )
            email_sent, email_error = send_email(email, subject, body)
            if not email_sent:
                app.logger.warning("Account created, but welcome email could not be sent: %s", email_error)

            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username or email already exists.")
        except Exception as exc:
            app.logger.exception("Registration failed")
            return render_template("register.html", error=f"Registration error: {exc}")

    return render_template("register.html")


@app.route('/export.csv')
@login_required
def export_csv():
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT amount, description, expense_date, category_id FROM expenses WHERE account_id = ? ORDER BY expense_date DESC", (session['account_id'],))
        rows = cursor.fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['amount', 'description', 'expense_date', 'category_id'])
        for r in rows:
            writer.writerow([r['amount'], r['description'], r['expense_date'], r['category_id']])
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=expenses.csv'
        connection.close()
        return response
    except Exception:
        return redirect(url_for('dashboard'))

@app.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    try:
        connection = get_connection()
        cursor = connection.cursor()

        if request.method == "POST":
            category_id = request.form.get("category_id", "")
            monthly_limit = request.form.get("monthly_limit", "")

            if not category_id or not monthly_limit:
                cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
                categories = cursor.fetchall()
                return render_template("budgets.html", categories=categories, error="Complete both fields to save a budget.")

            try:
                monthly_limit_value = float(monthly_limit)
                if monthly_limit_value <= 0:
                    raise ValueError
            except ValueError:
                cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
                categories = cursor.fetchall()
                return render_template("budgets.html", categories=categories, error="Enter a valid monthly budget.")

            cursor.execute("SELECT id FROM budgets WHERE account_id = ? AND category_id = ?", (session["account_id"], category_id))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE budgets SET monthly_limit = ? WHERE id = ?", (monthly_limit_value, existing["id"]))
            else:
                cursor.execute("INSERT INTO budgets (account_id, category_id, monthly_limit) VALUES (?, ?, ?)", (session["account_id"], category_id, monthly_limit_value))

            connection.commit()

        cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        cursor.execute("""
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
        """, (session["account_id"],))
        budgets = cursor.fetchall()
        connection.close()
        return render_template("budgets.html", categories=categories, budgets=budgets)
    except Exception:
        return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        # Get filter parameters
        category_filter = request.args.get("category", "")
        start_date = request.args.get("start_date", "")
        end_date = request.args.get("end_date", "")
        
        # Build query
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
        
        cursor.execute(query, params)
        expenses = cursor.fetchall()
        
        # Calculate totals
        total_query = "SELECT SUM(amount) FROM expenses WHERE account_id = ?"
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
        
        # Get category breakdown
        cursor.execute("""
            SELECT categories.id, category_name, SUM(amount) as total
            FROM expenses
            JOIN categories ON expenses.category_id = categories.id
            WHERE account_id = ?
            GROUP BY categories.id, category_name
            ORDER BY total DESC
        """, (session["account_id"],))
        category_stats = cursor.fetchall()
        
        # Get all categories for filter dropdown
        cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        
        # Get month stats
        cursor.execute("""
            SELECT strftime('%Y-%m', expense_date) as month, SUM(amount) as total
            FROM expenses
            WHERE account_id = ?
            GROUP BY month
            ORDER BY month DESC
            LIMIT 6
        """, (session["account_id"],))
        monthly_stats = cursor.fetchall()

        cursor.execute("""
            SELECT budgets.id, categories.category_name, budgets.monthly_limit,
                COALESCE(SUM(expenses.amount), 0) as spent
            FROM budgets
            JOIN categories ON budgets.category_id = categories.id
            LEFT JOIN expenses ON expenses.category_id = categories.id
                AND expenses.account_id = budgets.account_id
                AND strftime('%Y-%m', expenses.expense_date) = strftime('%Y-%m', 'now')
            WHERE budgets.account_id = ?
            GROUP BY budgets.id, categories.category_name, budgets.monthly_limit
            ORDER BY categories.category_name
        """, (session["account_id"],))
        budget_stats = cursor.fetchall()
        
        connection.close()
        
        return render_template(
            "dashboard.html",
            expenses=expenses,
            total=round(total, 2),
            login=session["login"],
            categories=categories,
            category_stats=category_stats,
            monthly_stats=monthly_stats,
            budget_stats=budget_stats,
            selected_category=category_filter,
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        return redirect(url_for("login"))

@app.route("/add", methods=["GET", "POST"])
@login_required
def add_expense():
    try:
        connection = get_connection()
        cursor = connection.cursor()

        if request.method == "POST":
            categories = get_categories()

            # Validate inputs
            try:
                amount = float(request.form.get("amount", 0))
                if amount <= 0:
                    raise ValueError("Amount must be greater than 0")
            except ValueError:
                connection.close()
                return render_template("add_expense.html", categories=categories, error="Invalid amount. Please enter a positive number.")
            
            description = request.form.get("description", "").strip()
            if not description or len(description) > 200:
                connection.close()
                return render_template("add_expense.html", categories=categories, error="Description required (max 200 characters).")
            
            expense_date = request.form.get("expense_date", "").strip()
            if not expense_date:
                connection.close()
                return render_template("add_expense.html", categories=categories, error="Date is required.")
            
            try:
                datetime.strptime(expense_date, "%Y-%m-%d")
            except ValueError:
                connection.close()
                return render_template("add_expense.html", categories=categories, error="Invalid date format. Use YYYY-MM-DD.")
            
            category_id = request.form.get("category_id", "")
            if not category_id:
                connection.close()
                return render_template("add_expense.html", categories=categories, error="Please select a category.")
            
            # Insert expense
            cursor.execute("""
                INSERT INTO expenses (amount, description, expense_date, account_id, category_id)
                VALUES (?, ?, ?, ?, ?)
            """, (amount, description, expense_date, session["account_id"], category_id))

            connection.commit()

            cursor.execute("SELECT category_name FROM categories WHERE id = ?", (category_id,))
            category_name = cursor.fetchone()["category_name"]
            cursor.execute("SELECT monthly_limit FROM budgets WHERE account_id = ? AND category_id = ?", (session["account_id"], category_id))
            budget = cursor.fetchone()
            if budget:
                new_total = get_monthly_category_total(session["account_id"], int(category_id), expense_date)
                notify_budget_if_needed(session["account_id"], int(category_id), category_name, expense_date, new_total, budget["monthly_limit"])

            connection.close()
            return redirect(url_for("dashboard"))

        # GET request
        cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        connection.close()

        return render_template("add_expense.html", categories=categories)
    except Exception as e:
        return redirect(url_for("dashboard"))

@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Verify ownership
        cursor.execute("SELECT account_id FROM expenses WHERE id = ?", (expense_id,))
        expense = cursor.fetchone()
        
        if not expense or expense["account_id"] != session["account_id"]:
            connection.close()
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            categories = get_categories()
            expense_data = get_expense_for_account(expense_id, session["account_id"])
            if not expense_data:
                connection.close()
                return redirect(url_for("dashboard"))

            # Validate inputs
            try:
                amount = float(request.form.get("amount", 0))
                if amount <= 0:
                    raise ValueError("Amount must be greater than 0")
            except ValueError:
                connection.close()
                return render_template("edit_expense.html", expense=expense_data, categories=categories, error="Invalid amount.", expense_id=expense_id)
            
            description = request.form.get("description", "").strip()
            if not description or len(description) > 200:
                connection.close()
                return render_template("edit_expense.html", expense=expense_data, categories=categories, error="Description required (max 200 characters).", expense_id=expense_id)
            
            expense_date = request.form.get("expense_date", "").strip()
            if not expense_date:
                connection.close()
                return render_template("edit_expense.html", expense=expense_data, categories=categories, error="Date is required.", expense_id=expense_id)

            try:
                datetime.strptime(expense_date, "%Y-%m-%d")
            except ValueError:
                connection.close()
                return render_template("edit_expense.html", expense=expense_data, categories=categories, error="Invalid date format. Use YYYY-MM-DD.", expense_id=expense_id)
            
            category_id = request.form.get("category_id", "")
            if not category_id:
                connection.close()
                return render_template("edit_expense.html", expense=expense_data, categories=categories, error="Please select a category.", expense_id=expense_id)
            
            # Update expense
            cursor.execute("""
                UPDATE expenses 
                SET amount = ?, description = ?, expense_date = ?, category_id = ?
                WHERE id = ? AND account_id = ?
            """, (amount, description, expense_date, category_id, expense_id, session["account_id"]))

            connection.commit()
            cursor.execute("SELECT category_name FROM categories WHERE id = ?", (category_id,))
            category_name = cursor.fetchone()["category_name"]
            cursor.execute("SELECT monthly_limit FROM budgets WHERE account_id = ? AND category_id = ?", (session["account_id"], category_id))
            budget = cursor.fetchone()
            if budget:
                new_total = get_monthly_category_total(session["account_id"], int(category_id), expense_date)
                notify_budget_if_needed(session["account_id"], int(category_id), category_name, expense_date, new_total, budget["monthly_limit"])

            connection.close()
            return redirect(url_for("dashboard"))

        # GET request - load current expense data
        cursor.execute("""
            SELECT expenses.id, amount, description, expense_date, category_id
            FROM expenses
            WHERE id = ? AND account_id = ?
        """, (expense_id, session["account_id"]))
        
        expense_data = cursor.fetchone()
        cursor.execute("SELECT id, category_name FROM categories ORDER BY category_name")
        categories = cursor.fetchall()
        connection.close()

        if not expense_data:
            return redirect(url_for("dashboard"))

        return render_template("edit_expense.html", expense=expense_data, categories=categories, expense_id=expense_id)
    except Exception as e:
        return redirect(url_for("dashboard"))

@app.route("/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Verify ownership before deleting
        cursor.execute("SELECT account_id FROM expenses WHERE id = ?", (expense_id,))
        expense = cursor.fetchone()
        
        if expense and expense["account_id"] == session["account_id"]:
            cursor.execute("DELETE FROM expenses WHERE id = ? AND account_id = ?", (expense_id, session["account_id"]))
            connection.commit()

        connection.close()
        return redirect(url_for("dashboard"))
    except Exception as e:
        return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
