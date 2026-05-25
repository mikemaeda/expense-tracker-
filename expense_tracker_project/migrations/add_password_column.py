import sqlite3

DB = 'expense_tracker.db'

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Check if column exists
cur.execute("PRAGMA table_info(accounts)")
cols = [r[1] for r in cur.fetchall()]
if 'password_hash' not in cols:
    print('Adding password_hash column to accounts')
    cur.execute('ALTER TABLE accounts ADD COLUMN password_hash TEXT')
    conn.commit()
else:
    print('password_hash column already exists')

# Optionally set a default password for sample accounts that don't have it (not recommended for production)
# Here we skip setting defaults to avoid accidentally weakening security.

conn.close()
print('Migration complete')
