from app import DEFAULT_BADGES, Badge, User, app, db

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

    db.session.commit()
    print("Seed complete. The database contains the admin account and default badges.")
    print("Admin: ADMIN-001 / Admin123!")
    print("Use the admin Student CSV tool to add student accounts.")
