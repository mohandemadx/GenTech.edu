# GenTech

## Project structure

```text
GenTech.edu/
├── app.py                 # Flask app, SQLAlchemy models, authentication, imports, and routes
├── seed.py                # Creates demo users, badges, and sample grades
├── requirements.txt
├── grades.db              # Generated SQLite database (do not commit)
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

Open `http://127.0.0.1:5000`. The seed script is idempotent and prints the demo credentials:

- Admin: `ADMIN-001` / `Admin123!`
- Students: `STU-1001`, `STU-1002`, or `STU-1003` / `Welcome123!`

Set a strong `SECRET_KEY` and replace the demo passwords before deploying. You can also set `DATABASE_URL` to point to another SQLite database.

Bulk files must contain these columns:

```text
student_id, assessment_name, assessment_type, score, max_score
```

`assessment_type` accepts `quiz`, `exam`, or `assignment`. Existing assessment/student grade pairs are updated, and exam scores of at least 90% or quiz scores of 100% automatically unlock their badges.

To add students after the initial seed, log in as `ADMIN-001`, open the admin dashboard, and use **Import data > Student roster**. The roster file must contain:

```text
student_id,name,email,password
```

The seed script creates only the administrator and default badges. It does not create demo students or grades, so the roster import is the source of student accounts.

Students can change their password from the dashboard by entering their current password and a new password of at least 8 characters. The new password must be confirmed and must differ from the current password.
