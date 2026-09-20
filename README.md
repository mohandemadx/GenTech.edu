# GenTech Portal

## Project structure

```text
GenTech.edu/
├── app.py                 # Flask app, SQLAlchemy models, authentication, imports, and routes
├── seed.py                # Creates demo users, badges, and sample grades
├── requirements.txt
├── static/
│   └── logo-placeholder.svg # Replace this with the final GenTech logo
└── templates/
    ├── login.html         # Shared login screen
    ├── dashboard.html     # Student gradebook and trophy case
    └── admin.html         # Bulk upload and manual administration tools
```

## Setup and run

```powershell
python -m pip install -r requirements.txt
python seed.py
python app.py
```

Open `http://127.0.0.1:5000`. The reset seed script recreates the database and prints the administrator credentials:

- Admin 1: `ADMIN-001` / `Admin123!`
- Admin 2: `ADMIN-002` / `Instructor123!`

Set a strong `SECRET_KEY` and replace the demo passwords before deploying. You can also set `DATABASE_URL` to point to another SQLite database.

For local PostgreSQL development, set the variables in your shell using the values in `.env.example`. Never commit `.env` or paste a real database URL into source files. For Render, add `SECRET_KEY`, `DATABASE_URL`, and `COOKIE_SECURE=1` in the service's Environment settings.

Bulk files must contain these columns:

```text
student_id, assessment_name, assessment_type, score, max_score
```

`assessment_type` accepts `quiz`, `exam`, or `assignment`. Existing assessment/student grade pairs are updated, and exam scores of at least 90% or quiz scores of 100% automatically unlock their badges.

To add students after the initial seed, log in as `ADMIN-001`, open the admin dashboard, and use **Import data > Student roster**. The roster file must contain:

```text
student_id,name,email,password
```

The seed script **deletes all existing tables and data** before recreating the administrator accounts and 20 badges. It does not create students or grades, so the roster import is the source of student accounts. Back up `grades.db` before running it.

Students can change their password from the dashboard by entering their current password and a new password of at least 8 characters. The new password must be confirmed and must differ from the current password.

## Live project improvement roadmap

Use this checklist when planning future updates to the live GenTech Portal. Complete backups before making production changes, and test changes with a separate development database first.

### Phase 1: Protect the live system

- [ ] Create automated daily SQLite backups.
- [ ] Create a backup before every grade or student import.
- [ ] Keep multiple dated backup copies outside GitHub.
- [ ] Test restoring a backup.
- [ ] Replace all default admin passwords with strong private passwords.
- [ ] Add CSRF protection to all state-changing forms.
- [ ] Enforce secure, HTTP-only, SameSite session cookies.
- [ ] Add session expiration and logout-from-all-devices support.
- [ ] Add login rate limiting and temporary account lockout.
- [ ] Require students to change temporary passwords on first login.
- [ ] Add an admin password-reset workflow for students.

### Phase 2: Improve administration

- [ ] Add student search and filtering.
- [ ] Allow admins to edit student names and email addresses.
- [ ] Add account disable/deactivate support.
- [ ] Add student password reset support.
- [ ] Add safe student-list export.
- [ ] Add grade filtering by student, assessment type, and date.
- [ ] Allow admins to edit and delete incorrect grades.
- [ ] Record who changed a grade and when.
- [ ] Add CSV/Excel preview before committing an import.
- [ ] Show row-level import validation errors.
- [ ] Create an automatic backup before each import.
- [ ] Add admin badge creation and editing.
- [ ] Add configurable automatic badge thresholds.
- [ ] Add badge-award history.

### Phase 3: Improve the student experience

- [ ] Add grade filters by assessment category.
- [ ] Show averages for quizzes, exams, and assignments separately.
- [ ] Add grade trends over time.
- [ ] Show points needed for the next badge or milestone.
- [ ] Add recent activity.
- [ ] Add a student profile page.
- [ ] Add instructor comments per assessment.
- [ ] Add private teacher-student questions or messages.
- [ ] Improve keyboard navigation and screen-reader labels.
- [ ] Verify color contrast and mobile layouts.

### Phase 4: Improve privacy

- [ ] Store only data required for the educational purpose.
- [ ] Ensure students can access only their own grades and badges.
- [ ] Ensure student data never appears in public URLs or unauthenticated pages.
- [ ] Add an audit log for logins, imports, grade changes, badge awards, and password actions.
- [ ] Define retention periods for inactive accounts, grades, audit logs, and backups.
- [ ] Add a privacy notice explaining collection, access, use, and retention.
- [ ] Keep all secrets in PythonAnywhere environment variables.
- [ ] Never commit `.env`, databases, backups, or real student CSV files.
- [ ] Rotate credentials if they are ever shared or exposed.

### Phase 5: Technical maintenance

- [ ] Add Flask-Migrate/Alembic database migrations.
- [ ] Keep development and production databases separate.
- [ ] Add automated tests for authentication and authorization.
- [ ] Add tests for CSV validation and imports.
- [ ] Add tests for password changes and badge rules.
- [ ] Add tests confirming students cannot access admin data.
- [ ] Monitor the `/health` endpoint.
- [ ] Update dependencies regularly and test updates locally.
- [ ] Review PythonAnywhere logs after every deployment.

## Safe update workflow

Follow this process for every future production update:

```text
1. Back up the production database.
2. Make the change locally.
3. Test using a separate development database.
4. Review the code and affected screens.
5. Commit and push the change to GitHub.
6. Pull the update on PythonAnywhere.
7. Install any dependency changes.
8. Run migrations, if applicable.
9. Reload the PythonAnywhere web application.
10. Test login, student access, admin access, and /health.
11. Confirm the live application is working.
```

### Critical warning

The current `seed.py` script is destructive. It drops all existing tables and data before recreating the database. Never run it against production after real student data has been imported unless a full reset is explicitly intended and a verified backup exists.

## Recommended implementation order

1. Automated backups
2. CSRF protection
3. First-login password changes
4. Admin password reset
5. Import preview and validation
6. Audit logging
7. Improved grade editing
8. Badge management UI
9. Student feedback and comments
10. Database migrations

## Render + PostgreSQL deployment

The application supports PostgreSQL through `DATABASE_URL`. In Render, configure:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn app:app --bind 0.0.0.0:$PORT
```

Set these Render environment variables:

```text
SECRET_KEY=<long-random-production-secret>
DATABASE_URL=<PostgreSQL internal database URL>
COOKIE_SECURE=1
```

The `/health` endpoint verifies that the application is running and can reach the configured database. Run `python seed.py` once against the production `DATABASE_URL` to create the administrator and default badges; do not commit the database or real credentials to GitHub.
