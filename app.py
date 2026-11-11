import csv
import io
import os
import math
import calendar
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

import pandas as pd
from backup_db import BackupError, create_backup
from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import text, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
database_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'grades.db'}")
if database_url.startswith(("postgres://", "postgresql://")):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
csrf = CSRFProtect(app)
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    grades = db.relationship("Grade", back_populates="student", cascade="all, delete-orphan")
    badges = db.relationship("StudentBadge", back_populates="student", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    max_score = db.Column(db.Float, nullable=False)
    session_date = db.Column(db.Date, nullable=True)
    grades = db.relationship("Grade", back_populates="assessment", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("title", "type", name="uq_assessment_title_type"),)


class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessment.id"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    student = db.relationship("User", back_populates="grades")
    assessment = db.relationship("Assessment", back_populates="grades")
    __table_args__ = (UniqueConstraint("student_id", "assessment_id", name="uq_student_assessment"),)

    @property
    def percentage(self):
        return self.score / self.assessment.max_score * 100 if self.assessment.max_score else 0


class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon_name = db.Column(db.String(20), nullable=False, default="award")
    criteria_type = db.Column(db.String(30), nullable=False, default="manual")
    awards = db.relationship("StudentBadge", back_populates="badge", cascade="all, delete-orphan")


class StudentBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badge.id"), nullable=False)
    unlocked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    student = db.relationship("User", back_populates="badges")
    badge = db.relationship("Badge", back_populates="awards")
    __table_args__ = (UniqueConstraint("student_id", "badge_id", name="uq_student_badge"),)


class RecognitionSelection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    period_type = db.Column(db.String(10), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    selected_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    selected_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    student = db.relationship("User", foreign_keys=[student_id])
    selected_by = db.relationship("User", foreign_keys=[selected_by_id])
    __table_args__ = (
        UniqueConstraint("period_type", "period_start", name="uq_recognition_period"),
    )


DEFAULT_BADGES = [
    {"name": "Top Scorer", "description": "Scored 90% or higher on an exam.", "icon_name": "star", "criteria_type": "exam_90"},
    {"name": "Perfect Quiz", "description": "Scored 100% on a quiz.", "icon_name": "sparkles", "criteria_type": "quiz_100"},
    {"name": "Exam Excellence", "description": "Scored 100% on an exam.", "icon_name": "trophy", "criteria_type": "exam_100"},
    {"name": "Quiz Ace", "description": "Scored at least 90% on a quiz.", "icon_name": "target", "criteria_type": "quiz_90"},
    {"name": "Assignment Pro", "description": "Scored at least 90% on an assignment.", "icon_name": "book", "criteria_type": "assignment_90"},
    {"name": "Class Champion", "description": "A badge awarded personally by your instructor.", "icon_name": "crown", "criteria_type": "manual"},
    {"name": "Outstanding Effort", "description": "A badge awarded personally by your instructor.", "icon_name": "medal", "criteria_type": "manual"},
    {"name": "Creative Thinker", "description": "A badge awarded personally by your instructor.", "icon_name": "lightbulb", "criteria_type": "manual"},
    {"name": "Helpful Classmate", "description": "A badge awarded personally by your instructor.", "icon_name": "hand", "criteria_type": "manual"},
    {"name": "Curious Learner", "description": "A badge awarded personally by your instructor.", "icon_name": "search", "criteria_type": "manual"},
    {"name": "Leadership Badge", "description": "A badge awarded personally by your instructor.", "icon_name": "flag", "criteria_type": "manual"},
    {"name": "Persistence Award", "description": "A badge awarded personally by your instructor.", "icon_name": "mountain", "criteria_type": "manual"},
    {"name": "Growth Mindset", "description": "A badge awarded personally by your instructor.", "icon_name": "seedling", "criteria_type": "manual"},
    {"name": "Team Builder", "description": "A badge awarded personally by your instructor.", "icon_name": "users", "criteria_type": "manual"},
    {"name": "Discussion Leader", "description": "A badge awarded personally by your instructor.", "icon_name": "chat", "criteria_type": "manual"},
    {"name": "Research Star", "description": "A badge awarded personally by your instructor.", "icon_name": "microscope", "criteria_type": "manual"},
    {"name": "Reliable Contributor", "description": "A badge awarded personally by your instructor.", "icon_name": "check", "criteria_type": "manual"},
    {"name": "Kindness Counts", "description": "A badge awarded personally by your instructor.", "icon_name": "heart", "criteria_type": "manual"},
    {"name": "Problem Solver", "description": "A badge awarded personally by your instructor.", "icon_name": "puzzle", "criteria_type": "manual"},
    {"name": "Course Finisher", "description": "A badge awarded personally by your instructor.", "icon_name": "flag-checkered", "criteria_type": "manual"},
]


def period_bounds(period_type, reference_date=None):
    reference_date = reference_date or date.today()
    if period_type == "weekly":
        start = reference_date - timedelta(days=reference_date.weekday())
        return start, start + timedelta(days=6)
    if period_type == "monthly":
        start = reference_date.replace(day=1)
        last_day = calendar.monthrange(start.year, start.month)[1]
        return start, start.replace(day=last_day)
    raise ValueError("Period type must be weekly or monthly.")


def get_period_recognition(period_type, start_date, end_date):
    grades = (
        Grade.query.join(Assessment)
        .join(User, Grade.student_id == User.id)
        .filter(
            User.role == "student",
            Assessment.session_date >= start_date,
            Assessment.session_date <= end_date,
            Assessment.session_date.isnot(None),
        )
        .all()
    )
    per_student = {}
    for grade in grades:
        if grade.assessment.max_score <= 0:
            continue
        entry = per_student.setdefault(
            grade.student_id,
            {"student": grade.student, "percentages": []},
        )
        entry["percentages"].append(grade.percentage)

    rankings = [
        {
            "student": entry["student"],
            "average": sum(entry["percentages"]) / len(entry["percentages"]),
            "grade_count": len(entry["percentages"]),
        }
        for entry in per_student.values()
    ]
    rankings.sort(key=lambda row: (-row["average"], row["student"].name.casefold()))

    leaders = []
    selection = None
    winner = None
    if rankings:
        highest_average = rankings[0]["average"]
        leaders = [
            row for row in rankings
            if math.isclose(row["average"], highest_average, rel_tol=1e-9, abs_tol=1e-9)
        ]
        selection = RecognitionSelection.query.filter_by(
            period_type=period_type,
            period_start=start_date,
        ).first()
        if len(leaders) == 1:
            winner = leaders[0]
        elif selection:
            winner = next(
                (row for row in leaders if row["student"].id == selection.student_id),
                None,
            )

    return {
        "period_type": period_type,
        "start": start_date,
        "end": end_date,
        "rankings": rankings,
        "leaders": leaders,
        "winner": winner,
        "selection": selection,
        "needs_admin_choice": len(leaders) > 1 and winner is None,
    }


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user.role != "admin":
            flash("That area is reserved for instructors.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def award_badge(user, badge_name):
    if not user:
        raise ValueError("Student not found.")
    badge = Badge.query.filter_by(name=badge_name).first()
    if not badge:
        raise ValueError("Badge not found.")
    if not StudentBadge.query.filter_by(student_id=user.id, badge_id=badge.id).first():
        db.session.add(StudentBadge(student=user, badge=badge))


def evaluate_badges(user, assessment=None):
    rules = {
        "exam_90": lambda grade: grade.assessment.type == "exam" and grade.percentage >= 90,
        "exam_100": lambda grade: grade.assessment.type == "exam" and grade.percentage >= 100,
        "quiz_100": lambda grade: grade.assessment.type == "quiz" and grade.percentage >= 100,
        "quiz_90": lambda grade: grade.assessment.type == "quiz" and grade.percentage >= 90,
        "assignment_90": lambda grade: grade.assessment.type == "assignment" and grade.percentage >= 90,
    }
    grades = Grade.query.filter_by(student_id=user.id).all()
    for badge in Badge.query.filter(Badge.criteria_type.in_(rules)).all():
        awarded = StudentBadge.query.filter_by(student_id=user.id, badge_id=badge.id).first()
        qualifies = any(rules[badge.criteria_type](grade) for grade in grades)
        if qualifies and not awarded:
            db.session.add(StudentBadge(student=user, badge=badge))
        elif not qualifies and awarded:
            db.session.delete(awarded)


def parse_session_date(value):
    if isinstance(value, datetime):
        session_date = value.date()
    elif isinstance(value, date):
        session_date = value
    else:
        try:
            session_date = date.fromisoformat(str(value).strip())
        except (TypeError, ValueError) as error:
            raise ValueError("session_date must use YYYY-MM-DD format.") from error
    if session_date.weekday() != 0:
        raise ValueError("Session date must be a Monday.")
    return session_date


def upsert_grade(student, title, assessment_type, score, max_score, session_date):
    assessment_type = assessment_type.strip().lower()
    if assessment_type not in {"quiz", "exam", "assignment"}:
        raise ValueError("assessment_type must be quiz, exam, or assignment")
    score = float(score)
    max_score = float(max_score)
    if not math.isfinite(score) or not math.isfinite(max_score) or max_score <= 0 or score < 0 or score > max_score:
        raise ValueError("score must be between 0 and max_score")
    session_date = parse_session_date(session_date)
    assessment = Assessment.query.filter_by(title=title.strip(), type=assessment_type).first()
    if not assessment:
        assessment = Assessment(title=title.strip(), type=assessment_type, max_score=max_score, session_date=session_date)
        db.session.add(assessment)
        db.session.flush()
    else:
        assessment.max_score = max_score
        assessment.session_date = session_date
    grade = Grade.query.filter_by(student_id=student.id, assessment_id=assessment.id).first()
    if grade:
        grade.score = score
    else:
        grade = Grade(student=student, assessment=assessment, score=score)
        db.session.add(grade)
    db.session.flush()
    evaluate_badges(student, assessment)


@app.route("/", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("admin" if current_user().role == "admin" else "dashboard"))
    if request.method == "POST":
        user = User.query.filter_by(student_id=request.form.get("student_id", "").strip()).first()
        if user and user.check_password(request.form.get("password", "")):
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("admin" if user.role == "admin" else "dashboard"))
        flash("We could not match that student ID and password.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    return (
        render_template(
            "error.html",
            title="Form expired",
            message="This form could not be verified. Reload the page and try again.",
        ),
        400,
    )


@app.get("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return {"status": "ok"}, 200


@app.route("/admin/student-password", methods=["GET", "POST"])
@admin_required
def admin_student_password():
    if request.method == "POST":
        try:
            student = db.session.get(User, int(request.form.get("student_id", "")))
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not student or student.role != "student":
                raise ValueError("Select a valid student account.")
            if len(new_password) < 8:
                raise ValueError("The new password must be at least 8 characters long.")
            if new_password != confirm_password:
                raise ValueError("The new passwords do not match.")

            create_backup()
            student.set_password(new_password)
            db.session.commit()
            flash(f"Password reset for {student.name} ({student.student_id}).", "success")
            return redirect(url_for("admin"))
        except BackupError as error:
            db.session.rollback()
            flash(f"Password was not changed because a backup could not be created: {error}", "error")
        except (TypeError, ValueError) as error:
            db.session.rollback()
            flash(str(error), "error")

    students = User.query.filter_by(role="student").order_by(User.name).all()
    return render_template("admin_password.html", students=students)


@app.route("/admin/students/<int:student_id>", methods=["GET", "POST"])
@admin_required
def admin_student_profile(student_id):
    student = db.session.get(User, student_id)
    if not student or student.role != "student":
        flash("Student account not found.", "error")
        return redirect(url_for("admin"))

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "profile":
                name = request.form.get("name", "").strip()
                email = request.form.get("email", "").strip()
                if not name or not email:
                    raise ValueError("Name and email are required.")
                email_owner = User.query.filter(User.email == email, User.id != student.id).first()
                if email_owner:
                    raise ValueError("That email address is already used by another account.")
                create_backup()
                student.name = name
                student.email = email
            elif action == "grade":
                grade = db.session.get(Grade, int(request.form.get("grade_id", "")))
                if not grade or grade.student_id != student.id:
                    raise ValueError("Grade not found for this student.")
                score = float(request.form.get("score", ""))
                if not math.isfinite(score) or score < 0 or score > grade.assessment.max_score:
                    raise ValueError("Score must be between 0 and the assessment max score.")
                create_backup()
                grade.score = score
                db.session.flush()
                evaluate_badges(student)
            elif action == "delete_grade":
                grade = db.session.get(Grade, int(request.form.get("grade_id", "")))
                if not grade or grade.student_id != student.id:
                    raise ValueError("Grade not found for this student.")
                create_backup()
                db.session.delete(grade)
                db.session.flush()
                evaluate_badges(student)
            elif action == "award_badge":
                badge = db.session.get(Badge, int(request.form.get("badge_id", "")))
                if not badge or badge.criteria_type != "manual":
                    raise ValueError("Select a valid admin-awarded badge.")
                create_backup()
                award_badge(student, badge.name)
            elif action == "remove_badge":
                award = db.session.get(StudentBadge, int(request.form.get("student_badge_id", "")))
                if not award or award.student_id != student.id or award.badge.criteria_type != "manual":
                    raise ValueError("Only a manually awarded badge for this student can be removed here.")
                create_backup()
                db.session.delete(award)
            else:
                raise ValueError("Unknown profile action.")
            db.session.commit()
            flash("Student profile updated.", "success")
        except BackupError as error:
            db.session.rollback()
            flash(f"Change was not saved because a backup could not be created: {error}", "error")
        except (TypeError, ValueError) as error:
            db.session.rollback()
            flash(str(error), "error")
        return redirect(url_for("admin_student_profile", student_id=student_id))

    grades = (
        Grade.query.filter_by(student_id=student.id)
        .join(Assessment)
        .order_by(Assessment.session_date.desc(), Assessment.title)
        .all()
    )
    all_badges = Badge.query.order_by(Badge.criteria_type, Badge.name).all()
    awards = {award.badge_id: award for award in student.badges}
    total_points = sum(grade.score for grade in grades)
    possible_points = sum(grade.assessment.max_score for grade in grades)
    average = total_points / possible_points * 100 if possible_points else 0
    return render_template(
        "admin_student_profile.html",
        student=student,
        grades=grades,
        badges=all_badges,
        awards=awards,
        total_points=total_points,
        average=average,
    )


@app.post("/admin/recognition")
@admin_required
def select_recognition_winner():
    try:
        period_type = request.form.get("period_type", "")
        period_start = date.fromisoformat(request.form.get("period_start", ""))
        student_id = int(request.form.get("student_id", ""))
        expected_start, period_end = period_bounds(period_type, period_start)
        if expected_start != period_start:
            raise ValueError("The selected period start date is invalid.")

        recognition = get_period_recognition(period_type, period_start, period_end)
        if len(recognition["leaders"]) < 2:
            raise ValueError("An administrator may select a winner only when the top average is tied.")
        if not any(row["student"].id == student_id for row in recognition["leaders"]):
            raise ValueError("Select one of the students tied for the highest period average.")

        create_backup()
        selection = RecognitionSelection.query.filter_by(
            period_type=period_type,
            period_start=period_start,
        ).first()
        if selection:
            selection.student_id = student_id
            selection.selected_by_id = current_user().id
            selection.selected_at = datetime.utcnow()
        else:
            selection = RecognitionSelection(
                period_type=period_type,
                period_start=period_start,
                student_id=student_id,
                selected_by_id=current_user().id,
            )
            db.session.add(selection)
        db.session.commit()
        flash("Recognition winner selected.", "success")
    except BackupError as error:
        db.session.rollback()
        flash(f"Winner was not saved because a backup could not be created: {error}", "error")
    except (TypeError, ValueError) as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("admin") + "?tab=recognition")


@app.post("/change-password")
@login_required
def change_password():
    user = current_user()
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not user.check_password(current_password):
        flash("Your current password is incorrect.", "error")
    elif len(new_password) < 8:
        flash("Your new password must be at least 8 characters long.", "error")
    elif new_password != confirm_password:
        flash("The new passwords do not match.", "error")
    elif user.check_password(new_password):
        flash("Your new password must be different from your current password.", "error")
    else:
        try:
            create_backup()
            user.set_password(new_password)
            db.session.commit()
            flash("Your password was changed successfully.", "success")
        except BackupError as error:
            db.session.rollback()
            flash(f"Password change was not saved: {error}", "error")
    return redirect(url_for("dashboard"))


@app.get("/dashboard")
@login_required
def dashboard():
    user = current_user()
    grades = Grade.query.filter_by(student_id=user.id).join(Assessment).order_by(Assessment.type, Assessment.title).all()
    total_points = sum(grade.score for grade in grades)
    possible_points = sum(grade.assessment.max_score for grade in grades)
    average = total_points / possible_points * 100 if possible_points else 0
    all_badges = Badge.query.order_by(Badge.id).all()
    unlocked = {award.badge_id: award for award in user.badges}
    today = date.today()
    week_start, week_end = period_bounds("weekly", today)
    month_start, month_end = period_bounds("monthly", today)
    weekly_recognition = get_period_recognition("weekly", week_start, week_end)
    monthly_recognition = get_period_recognition("monthly", month_start, month_end)
    return render_template(
        "dashboard.html",
        user=user,
        grades=grades,
        average=average,
        total_points=total_points,
        all_badges=all_badges,
        unlocked=unlocked,
        weekly_recognition=weekly_recognition,
        monthly_recognition=monthly_recognition,
    )


@app.get("/admin/students/export")
@admin_required
def export_students():
    def safe_csv_value(value):
        value = value or ""
        if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["student_id", "name", "email"])
    students = User.query.filter_by(role="student").order_by(User.name, User.student_id).all()
    for student in students:
        writer.writerow(
            [
                safe_csv_value(student.student_id),
                safe_csv_value(student.name),
                safe_csv_value(student.email),
            ]
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=GenTech-students.csv"},
    )


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action in {"upload", "students", "add_student", "grade", "badge"}:
                create_backup()
            if action == "upload":
                upload = request.files.get("file")
                if not upload or not upload.filename:
                    raise ValueError("Choose a CSV or Excel file first.")
                suffix = Path(upload.filename).suffix.lower()
                if suffix not in {".csv", ".xlsx"}:
                    raise ValueError("Only .csv and .xlsx files are supported.")
                frame = pd.read_csv(upload) if suffix == ".csv" else pd.read_excel(upload)
                required = {"student_id", "assessment_name", "assessment_type", "score", "max_score", "session_date"}
                missing = required - set(frame.columns)
                if missing:
                    raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
                imported = 0
                for row in frame.to_dict("records"):
                    student = User.query.filter_by(student_id=str(row["student_id"]).strip()).first()
                    if not student or student.role != "student":
                        raise ValueError(f"Unknown student ID: {row['student_id']}")
                    upsert_grade(
                        student,
                        row["assessment_name"],
                        row["assessment_type"],
                        row["score"],
                        row["max_score"],
                        row["session_date"],
                    )
                    imported += 1
                db.session.commit()
                flash(f"Imported {imported} grade record(s).", "success")
            elif action == "add_student":
                student_id = request.form.get("new_student_id", "").strip()
                name = request.form.get("new_student_name", "").strip()
                email = request.form.get("new_student_email", "").strip() or None
                password = request.form.get("new_student_password", "")
                confirm_password = request.form.get("new_student_confirm_password", "")
                if not student_id or not name or not password:
                    raise ValueError("Student ID, name, and password are required.")
                if len(student_id) > 50 or len(name) > 120 or (email and len(email) > 160):
                    raise ValueError("Student ID, name, or email is longer than the allowed limit.")
                if len(password) < 8:
                    raise ValueError("The password must be at least 8 characters long.")
                if password != confirm_password:
                    raise ValueError("The passwords do not match.")
                if User.query.filter_by(student_id=student_id).first():
                    raise ValueError("That student ID is already in use.")
                if email and User.query.filter_by(email=email).first():
                    raise ValueError("That email address is already in use.")
                student = User(student_id=student_id, name=name, email=email, role="student")
                student.set_password(password)
                db.session.add(student)
                db.session.commit()
                flash(f"Student account created for {student.name}.", "success")
            elif action == "students":
                upload = request.files.get("student_file")
                if not upload or not upload.filename:
                    raise ValueError("Choose a student CSV or Excel file first.")
                suffix = Path(upload.filename).suffix.lower()
                if suffix not in {".csv", ".xlsx"}:
                    raise ValueError("Only .csv and .xlsx files are supported.")
                frame = pd.read_csv(upload) if suffix == ".csv" else pd.read_excel(upload)
                required = {"student_id", "name", "email", "password"}
                missing = required - set(frame.columns)
                if missing:
                    raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
                imported = 0
                for row_number, row in enumerate(frame.to_dict("records"), start=2):
                    student_id = str(row["student_id"]).strip()
                    name = str(row["name"]).strip()
                    email = str(row["email"]).strip()
                    password = str(row["password"]).strip()
                    if not student_id or not name or not email or not password:
                        raise ValueError(f"Row {row_number}: student_id, name, email, and password are required.")
                    user = User.query.filter_by(student_id=student_id).first()
                    if user and user.role != "student":
                        raise ValueError(f"Row {row_number}: {student_id} belongs to an administrator.")
                    email_owner = User.query.filter(User.email == email, User.student_id != student_id).first()
                    if email_owner:
                        raise ValueError(f"Row {row_number}: email is already used by another account.")
                    if not user:
                        user = User(student_id=student_id, role="student")
                        db.session.add(user)
                    user.name = name
                    user.email = email
                    user.set_password(password)
                    imported += 1
                db.session.commit()
                flash(f"Imported {imported} student account(s).", "success")
            elif action == "grade":
                student = db.session.get(User, int(request.form["student_id"]))
                upsert_grade(
                    student,
                    request.form["assessment_name"],
                    request.form["assessment_type"],
                    request.form["score"],
                    request.form["max_score"],
                    request.form["session_date"],
                )
                db.session.commit()
                flash("Grade updated and badge rules evaluated.", "success")
            elif action == "badge":
                student = db.session.get(User, int(request.form["student_id"]))
                badge = db.session.get(Badge, int(request.form["badge_id"]))
                if not badge or badge.criteria_type != "manual":
                    raise ValueError("Select an admin-awarded badge.")
                award_badge(student, badge.name if badge else None)
                db.session.commit()
                flash("Badge awarded.", "success")
        except BackupError as error:
            db.session.rollback()
            flash(f"Change was not saved because a backup could not be created: {error}", "error")
        except (ValueError, TypeError, KeyError) as error:
            db.session.rollback()
            flash(str(error), "error")
        return redirect(url_for("admin"))
    students = User.query.filter_by(role="student").order_by(User.name).all()
    grades = Grade.query.join(User).join(Assessment).filter(User.role == "student").order_by(User.name, Assessment.title).all()
    today = date.today()
    week_start, week_end = period_bounds("weekly", today)
    month_start, month_end = period_bounds("monthly", today)
    return render_template(
        "admin.html",
        students=students,
        grades=grades,
        badges=Badge.query.order_by(Badge.name).all(),
        weekly_recognition=get_period_recognition("weekly", week_start, week_end),
        monthly_recognition=get_period_recognition("monthly", month_start, month_end),
    )


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
