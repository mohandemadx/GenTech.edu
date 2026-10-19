from sqlalchemy import inspect, text

from app import app, db


with app.app_context():
    if db.engine.dialect.name != "sqlite":
        raise RuntimeError("This migration script supports the current SQLite deployment only.")

    assessment_columns = {column["name"] for column in inspect(db.engine).get_columns("assessment")}
    if "session_date" in assessment_columns:
        print("Assessment session_date column already exists; no migration needed.")
    else:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE assessment ADD COLUMN session_date DATE"))
        print("Added nullable assessment.session_date. Existing assessments remain undated.")
