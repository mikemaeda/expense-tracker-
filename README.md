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

## Deployed app

Production URL:

```text
https://expense-tracker-app-mauve-gamma.vercel.app
```

The Vercel project is linked as `expense-tracker-app`.

Vercel uses the root `api/index.py` entrypoint and root `requirements.txt` file. The app still stores data in SQLite; on Vercel it defaults to `/tmp/expense_tracker.db`, which is temporary serverless storage. That is fine for demos and class/project review, but a real long-lived app should move the database to hosted storage such as Vercel Postgres, Neon, Supabase.
