from app import DEFAULT_BADGES, Assessment, Badge, Grade, User, app, db, upsert_grade

with app.app_context():
    db.create_all()
    for badge_data in DEFAULT_BADGES:
        if not Badge.query.filter_by(name=badge_data["name"]).first():
            db.session.add(Badge(**badge_data))

    admin = User.query.filter_by(student_id="ADMIN-001").first()
    if not admin:
        admin = User(student_id="ADMIN-001", name="Dr. Morgan Lee", email="admin@gentech.edu", role="admin")
        admin.set_password("Admin123!")
        db.session.add(admin)

    students = [
        ("STU-1001", "Avery Chen", "avery@example.com"),
        ("STU-1002", "Jordan Patel", "jordan@example.com"),
        ("STU-1003", "Sam Rivera", "sam@example.com"),
    ]
    for student_id, name, email in students:
        if not User.query.filter_by(student_id=student_id).first():
            student = User(student_id=student_id, name=name, email=email, role="student")
            student.set_password("Welcome123!")
            db.session.add(student)
    db.session.commit()

    sample_grades = [
        ("STU-1001", "Quiz 1", "quiz", 10, 10),
        ("STU-1001", "Midterm Exam", "exam", 92, 100),
        ("STU-1001", "Research Assignment", "assignment", 45, 50),
        ("STU-1002", "Quiz 1", "quiz", 8, 10),
        ("STU-1002", "Midterm Exam", "exam", 84, 100),
        ("STU-1003", "Quiz 1", "quiz", 9, 10),
    ]
    for student_id, title, assessment_type, score, max_score in sample_grades:
        student = User.query.filter_by(student_id=student_id).first()
        upsert_grade(student, title, assessment_type, score, max_score)
    db.session.commit()
    print("Seed complete.")
    print("Admin: ADMIN-001 / Admin123!")
    print("Students: STU-1001, STU-1002, STU-1003 / Welcome123!")
