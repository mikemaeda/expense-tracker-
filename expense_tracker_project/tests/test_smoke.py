import sqlite3
import time
from datetime import date

import requests

BASE = "http://127.0.0.1:5000"
DB_PATH = "expense_tracker.db"


def find_account_id(conn, login):
    cur = conn.cursor()
    cur.execute("SELECT id FROM accounts WHERE login = ?", (login,))
    row = cur.fetchone()
    return row[0] if row else None


def find_expense_by_description(conn, account_id, desc):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, amount, description
        FROM expenses
        WHERE account_id = ? AND description = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (account_id, desc),
    )
    return cur.fetchone()


if __name__ == "__main__":
    session = requests.Session()
    username = f"smoke_user_{int(time.time())}"
    password = "TestPass123!"

    print("Registering user", username)
    response = session.post(
        BASE + "/register",
        data={
            "login": username,
            "email": f"{username}@example.com",
            "password": password,
            "password_confirm": password,
        },
        allow_redirects=True,
    )
    if response.status_code not in (200, 302):
        raise SystemExit(f"Register failed: {response.status_code}")

    print("Logging in as", username)
    response = session.post(BASE + "/", data={"login": username, "password": password}, allow_redirects=True)
    if response.status_code != 200:
        raise SystemExit(f"Login failed: {response.status_code}")

    desc = f"smoke-test-{int(time.time())}"
    response = session.post(
        BASE + "/add",
        data={
            "amount": "12.34",
            "description": desc,
            "expense_date": date.today().isoformat(),
            "category_id": "1",
        },
        allow_redirects=True,
    )
    if response.status_code != 200:
        raise SystemExit(f"Add expense failed: {response.status_code}")

    conn = sqlite3.connect(DB_PATH)
    account_id = find_account_id(conn, username)
    if not account_id:
        raise SystemExit("Test account not found in DB")

    found = find_expense_by_description(conn, account_id, desc)
    if not found:
        raise SystemExit("Expense not found in DB")

    expense_id = found[0]
    new_desc = desc + "-edited"
    response = session.post(
        f"{BASE}/edit/{expense_id}",
        data={
            "amount": "15.00",
            "description": new_desc,
            "expense_date": date.today().isoformat(),
            "category_id": "1",
        },
        allow_redirects=True,
    )
    if response.status_code != 200:
        raise SystemExit(f"Edit failed: {response.status_code}")

    if not find_expense_by_description(conn, account_id, new_desc):
        raise SystemExit("Edited expense not found")

    response = session.post(f"{BASE}/delete/{expense_id}", allow_redirects=True)
    if response.status_code not in (200, 302):
        raise SystemExit(f"Delete failed: {response.status_code}")

    cur = conn.cursor()
    cur.execute("SELECT id FROM expenses WHERE id = ? AND account_id = ?", (expense_id, account_id))
    if cur.fetchone():
        raise SystemExit("Expense still exists after delete")

    conn.close()
    print("SMOKE TESTS PASSED")
