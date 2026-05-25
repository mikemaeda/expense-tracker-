import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'expense_tracker.db'

conn = sqlite3.connect(DB)
cur = conn.cursor()
print(f'database: {DB}')
print('tables:')
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(row)
print('\naccounts:')
for row in cur.execute('PRAGMA table_info(accounts)'):
    print(row)
print('\nbudgets:')
for row in cur.execute('PRAGMA table_info(budgets)'):
    print(row)
conn.close()
