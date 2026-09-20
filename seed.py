from app import DEFAULT_BADGES, Badge, User, app, db

with app.app_context():
    db.drop_all()
    db.create_all()
    db.session.add_all([Badge(**badge_data) for badge_data in DEFAULT_BADGES])

    administrators = [
        ("ADMIN-001", "Mohand Emad", "admin@gentech.edu", "Admin123!"),
        ("ADMIN-002", "GenTech Instructor", "instructor@gentech.edu", "Instructor123!"),
    ]
    for student_id, name, email, password in administrators:
        admin = User(student_id=student_id, name=name, email=email, role="admin")
        admin.set_password(password)
        db.session.add(admin)

    db.session.commit()
    print("Database reset complete.")
    print(f"Created {len(administrators)} admin accounts and {len(DEFAULT_BADGES)} badges.")
    print("Admin 1: ADMIN-001 / Admin123!")
    print("Admin 2: ADMIN-002 / Instructor123!")
    print("Use the admin Student CSV tool to add student accounts.")
