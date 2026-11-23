# NEXUS Education CRM

The application now runs on Django. It uses the existing SQLite database at
`instance/nexus.db` by default, so existing courses, students, teachers,
attendance, and payroll records remain available.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate --fake-initial
python manage.py runserver
```

Open `http://127.0.0.1:8000`. The initial administrator is `admin` with password
`Admin123!`; set `ADMIN_USERNAME` and `ADMIN_PASSWORD` before the first
migration to use different credentials. Set `SECRET_KEY` and `DEBUG=false` for
deployment. Environment settings can be placed in a `.env` file.

Set `DATABASE_URL` to a PostgreSQL connection URL to use PostgreSQL instead of
the default SQLite database.
