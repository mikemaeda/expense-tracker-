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

## Environment variables

Set values in `expense_tracker_project\.env`:

- `MAIL_SERVER` (e.g. `smtp.gmail.com`)
- `MAIL_PORT` (usually `587`)
- `MAIL_USERNAME` (your email address)
- `MAIL_PASSWORD` (SMTP password or Gmail app password)
- `MAIL_FROM` (sender address)
- `MAIL_USE_TLS` (`True` or `False`)
- `FLASK_SECRET_KEY` (session secret)
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

## GitHub push instructions

If you want to push this project to GitHub, run:

```powershell
cd "C:\Users\mhm5\Desktop\expense_tracker_project (1)"
git init
git add .
git commit -m "Initial expense tracker app"
git branch -M main
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

Replace `<username>` and `<repo>` with your GitHub account and repository name.

## Notes

- The app is located in the `expense_tracker_project` nested folder.
- Keep `.env` private and do not push it to GitHub.
- If Google sign-in is not configured, the login page will fall back to username/password.
