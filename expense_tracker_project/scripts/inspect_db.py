import sqlite3

conn = sqlite3.connect('expense_tracker.db')
cur = conn.cursor()
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
