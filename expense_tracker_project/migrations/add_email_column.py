import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'expense_tracker.db'

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute('PRAGMA table_info(accounts)')
columns = [row[1] for row in cur.fetchall()]
if 'email' not in columns:
    print('Adding email column to accounts table')
    cur.execute('ALTER TABLE accounts ADD COLUMN email TEXT')
    conn.commit()
else:
    print('email column already exists')

conn.close()
print('Migration complete')
