import requests
import sqlite3
import time
from datetime import date

BASE = 'http://127.0.0.1:5000'
DB_PATH = 'expense_tracker.db'




def find_account_id(conn, login):
    cur = conn.cursor()
    cur.execute('SELECT id FROM accounts WHERE login = ?', (login,))
    r = cur.fetchone()
    return r[0] if r else None


def find_expense_by_description(conn, account_id, desc):
    cur = conn.cursor()
    cur.execute('SELECT id, amount, description FROM expenses WHERE account_id = ? AND description = ? ORDER BY id DESC LIMIT 1', (account_id, desc))
    return cur.fetchone()


if __name__ == '__main__':
    session = requests.Session()

    # 0) Register a fresh test user
    username = f'smoke_user_{int(time.time())}'
    password = 'TestPass123!'
    print('Registering user', username)
    r = session.post(BASE + '/register', data={'login': username, 'email': 'smoke_user@example.com', 'password': password, 'password_confirm': password}, allow_redirects=True)
    if r.status_code not in (200, 302):
        print('Register failed:', r.status_code)
        raise SystemExit(1)

    # 1) Login
    print('Logging in as', username)
    r = session.post(BASE + '/', data={'login': username, 'password': password}, allow_redirects=True)
    if r.status_code != 200:
        print('Login request failed:', r.status_code)
        raise SystemExit(1)
    print('Logged in, dashboard status:', r.status_code)

    # 2) Add expense
    desc = f'smoke-test-{int(time.time())}'
    payload = {
        'amount': '12.34',
        'description': desc,
        'expense_date': date.today().isoformat(),
        'category_id': '1'
    }
    print('Adding expense', payload)
    r = session.post(BASE + '/add', data=payload, allow_redirects=True)
    if r.status_code != 200:
        print('Add expense failed:', r.status_code)
        raise SystemExit(1)
    print('Add returned', r.status_code)

    time.sleep(0.5)

    # 3) Verify DB for new expense
    conn = sqlite3.connect(DB_PATH)
    aid = find_account_id(conn, username)
    if not aid:
        print('Test account not found in DB')
        raise SystemExit(1)

    found = find_expense_by_description(conn, aid, desc)
    if not found:
        print('Expense not found in DB')
        raise SystemExit(1)

    expense_id = found[0]
    print('Found expense id', expense_id)

    # 4) Edit expense
    new_desc = desc + '-edited'
    print('Editing expense', expense_id)
    r = session.post(f"{BASE}/edit/{expense_id}", data={
        'amount': '15.00',
        'description': new_desc,
        'expense_date': date.today().isoformat(),
        'category_id': '1'
    }, allow_redirects=True)
    if r.status_code != 200:
        print('Edit failed', r.status_code)
        raise SystemExit(1)
    print('Edit returned', r.status_code)

    time.sleep(0.5)

    # verify edit
    found2 = find_expense_by_description(conn, aid, new_desc)
    if not found2:
        print('Edited expense not found')
        raise SystemExit(1)
    print('Edit verified')

    # 5) Delete expense
    print('Deleting expense', expense_id)
    r = session.post(f"{BASE}/delete/{expense_id}", allow_redirects=True)
    if r.status_code not in (200, 302):
        print('Delete failed', r.status_code)
        raise SystemExit(1)
    time.sleep(0.5)

    # verify deletion
    cur = conn.cursor()
    cur.execute('SELECT id FROM expenses WHERE id = ? AND account_id = ?', (expense_id, aid))
    if cur.fetchone():
        print('Expense still exists after delete')
        raise SystemExit(1)

    conn.close()
    print('\nSMOKE TESTS PASSED')
