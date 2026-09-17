import os
from datetime import datetime
from functools import wraps
from pathlib import Path

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{BASE_DIR / 'grades.db'}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
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


DEFAULT_BADGES = [
    {"name": "Top Scorer", "description": "Scored 90% or higher on an exam.", "icon_name": "star", "criteria_type": "exam_90"},
    {"name": "Perfect Quiz", "description": "Scored 100% on a quiz.", "icon_name": "sparkles", "criteria_type": "quiz_100"},
    {"name": "Class Champion", "description": "A badge awarded personally by your instructor.", "icon_name": "trophy", "criteria_type": "manual"},
]


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


def evaluate_badges(user, assessment):
    latest_grade = Grade.query.filter_by(student_id=user.id, assessment_id=assessment.id).first()
    if not latest_grade or not assessment.max_score:
        return
    percentage = latest_grade.score / assessment.max_score * 100
    if assessment.type == "exam" and percentage >= 90:
        award_badge(user, "Top Scorer")
    if assessment.type == "quiz" and percentage >= 100:
        award_badge(user, "Perfect Quiz")


def upsert_grade(student, title, assessment_type, score, max_score):
    assessment_type = assessment_type.strip().lower()
    if assessment_type not in {"quiz", "exam", "assignment"}:
        raise ValueError("assessment_type must be quiz, exam, or assignment")
    score = float(score)
    max_score = float(max_score)
    if max_score <= 0 or score < 0 or score > max_score:
        raise ValueError("score must be between 0 and max_score")
    assessment = Assessment.query.filter_by(title=title.strip(), type=assessment_type).first()
    if not assessment:
        assessment = Assessment(title=title.strip(), type=assessment_type, max_score=max_score)
        db.session.add(assessment)
        db.session.flush()
    else:
        assessment.max_score = max_score
    grade = Grade.query.filter_by(student_id=student.id, assessment_id=assessment.id).first()
    if grade:
        grade.score = score
    else:
        grade = Grade(student=student, assessment=assessment, score=score)
        db.session.add(grade)
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


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


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
    return render_template("dashboard.html", user=user, grades=grades, average=average, total_points=total_points, all_badges=all_badges, unlocked=unlocked)


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "upload":
                upload = request.files.get("file")
                if not upload or not upload.filename:
                    raise ValueError("Choose a CSV or Excel file first.")
                suffix = Path(upload.filename).suffix.lower()
                if suffix not in {".csv", ".xlsx"}:
                    raise ValueError("Only .csv and .xlsx files are supported.")
                frame = pd.read_csv(upload) if suffix == ".csv" else pd.read_excel(upload)
                required = {"student_id", "assessment_name", "assessment_type", "score", "max_score"}
                missing = required - set(frame.columns)
                if missing:
                    raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
                imported = 0
                for row in frame.to_dict("records"):
                    student = User.query.filter_by(student_id=str(row["student_id"]).strip()).first()
                    if not student or student.role != "student":
                        raise ValueError(f"Unknown student ID: {row['student_id']}")
                    upsert_grade(student, row["assessment_name"], row["assessment_type"], row["score"], row["max_score"])
                    imported += 1
                db.session.commit()
                flash(f"Imported {imported} grade record(s).", "success")
            elif action == "grade":
                student = db.session.get(User, int(request.form["student_id"]))
                upsert_grade(student, request.form["assessment_name"], request.form["assessment_type"], request.form["score"], request.form["max_score"])
                db.session.commit()
                flash("Grade updated and badge rules evaluated.", "success")
            elif action == "badge":
                student = db.session.get(User, int(request.form["student_id"]))
                badge = db.session.get(Badge, int(request.form["badge_id"]))
                award_badge(student, badge.name if badge else None)
                db.session.commit()
                flash("Badge awarded.", "success")
        except (ValueError, TypeError, KeyError) as error:
            db.session.rollback()
            flash(str(error), "error")
        return redirect(url_for("admin"))
    students = User.query.filter_by(role="student").order_by(User.name).all()
    grades = Grade.query.join(User).join(Assessment).filter(User.role == "student").order_by(User.name, Assessment.title).all()
    return render_template("admin.html", students=students, grades=grades, badges=Badge.query.order_by(Badge.name).all())


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
