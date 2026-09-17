# GradeAtlas

## Project structure

```text
GenTech.edu/
├── app.py                 # Flask app, SQLAlchemy models, authentication, imports, and routes
├── seed.py                # Creates demo users, badges, and sample grades
├── requirements.txt
├── grades.db              # Generated SQLite database (do not commit)
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
