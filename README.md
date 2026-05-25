# Expense Tracker

A Flask-based personal expense tracker with authentication, budget monitoring, email alerts, and Google sign-in support.

## What it does

- Register and sign in with username/password
- Sign in with Google OAuth
- Add, edit, and delete expenses
- Set category budgets and receive email budget alerts
- Export expenses to CSV
- Send welcome emails on account creation
- Track spending by category and month

## Technology

- Python 3
- Flask
- SQLite
- Authlib for Google OAuth
- SMTP email support via environment variables
- Vercel deployment

## Setup

1. Open a PowerShell terminal in the repository root:
   ```powershell
   cd "C:\Users\mhm5\Desktop\expense_tracker_project (1)"
   ```
2. Install dependencies (using the existing virtual environment if available):
   ```powershell
   & ".\.venv\Scripts\python.exe" -m pip install -r .\expense_tracker_project\requirements.txt
   ```
3. Copy `.env.example` to `.env` inside `expense_tracker_project` and fill in your values.
4. Run the app:
   ```powershell
   & ".\.venv\Scripts\python.exe" .\expense_tracker_project\app.py
   ```
5. Open http://127.0.0.1:5000 in your browser.

## Deployed app

Production URL:

```text
https://expense-tracker-app-mauve-gamma.vercel.app
```

The Vercel project is linked as `expense-tracker-app`.

Vercel uses the root `api/index.py` entrypoint and root `requirements.txt` file. The app still stores data in SQLite; on Vercel it defaults to `/tmp/expense_tracker.db`, which is temporary serverless storage. That is fine for demos and class/project review, but a real long-lived app should move the database to hosted storage such as Vercel Postgres, Neon, Supabase.
