# Expense Tracker

Expense Tracker is a Flask web application for managing personal spending, monitoring category budgets, and keeping expense history organized in one place. It supports account registration, secure password login, optional Google sign-in, budget alerts, CSV export, and a responsive dashboard for reviewing spending activity.

## Live Demo

Production app: https://expense-tracker-app-mauve-gamma.vercel.app

## Features

- User registration and password-based authentication
- Optional Google OAuth sign-in
- Add, edit, delete, and filter expenses
- Category-based spending summaries
- Monthly budget tracking by category
- Email notifications for welcome messages and budget alerts
- CSV export for expense records
- Responsive Flask/Jinja interface
- Vercel deployment support

## Tech Stack

- Python 3.12
- Flask
- SQLite
- Jinja templates
- Authlib for Google OAuth
- SMTP email integration
- Vercel for deployment

## Project Structure

```text
.
├── api/
│   └── index.py              # Vercel serverless entrypoint
├── expense_tracker_project/
│   ├── app.py                # Main Flask application
│   ├── static/               # CSS styles
│   ├── templates/            # Jinja HTML templates
│   ├── migrations/           # Local database migration helpers
│   ├── scripts/              # Utility scripts
│   ├── sql/                  # Database schema/sample data
│   └── tests/                # Smoke test script
├── requirements.txt          # Root dependencies for Vercel
├── vercel.json               # Vercel routing config
└── README.md
```

## Local Setup

1. Clone the repository:

   ```powershell
   git clone https://github.com/mikemaeda/expense-tracker-.git
   cd expense-tracker-
   ```

2. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Create a local environment file:

   ```powershell
   Copy-Item .\expense_tracker_project\.env.example .\expense_tracker_project\.env
   ```

5. Start the Flask app:

   ```powershell
   python .\expense_tracker_project\app.py
   ```

6. Open the app at http://127.0.0.1:5000.

## Environment Variables

Set these values in `expense_tracker_project/.env` for local development, or in the Vercel project settings for production:

| Variable | Purpose |
| --- | --- |
| `FLASK_SECRET_KEY` | Secret key used to sign Flask sessions |
| `DATABASE_PATH` | Optional SQLite database path |
| `MAIL_SERVER` | SMTP server host |
| `MAIL_PORT` | SMTP server port, usually `587` |
| `MAIL_USERNAME` | SMTP username/email |
| `MAIL_PASSWORD` | SMTP password or app password |
| `MAIL_FROM` | Sender email address |
| `MAIL_USE_TLS` | Enables TLS for SMTP |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |

## Deployment

This project is configured for Vercel using `api/index.py` as the serverless Flask entrypoint and `vercel.json` for routing.

The current production deployment is hosted at:

```text
https://expense-tracker-app-mauve-gamma.vercel.app
```

## Data Persistence Note

The deployed version currently uses SQLite. On Vercel, SQLite is stored in temporary serverless storage, so it is suitable for demos and project review but not ideal for long-term production data. A production-ready version should move persistence to a hosted database such as Vercel Postgres, Neon, Supabase, or Turso.

## Status

The app is deployed and functional. Current priority improvements would be persistent hosted storage, stronger automated tests, and cleaner production email/OAuth configuration.
