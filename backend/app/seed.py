"""With `python -m app.seed --demo`, create the VAICS Consulting organisation and demo users.
Demo passwords come from DEMO_PASSWORD (env); nothing secret is hard-coded."""
import os, sys
from .core.db import SessionLocal, Base, engine
from .core.security import hash_password
from .models import Organization, User, now

def demo(db, password: str):
    org = db.query(Organization).filter_by(slug="vaics-consulting").first()
    if not org:
        org = Organization(name="VAICS Consulting", slug="vaics-consulting", country="IN", region="in", status="active", currency="INR")
        db.add(org); db.flush()
    people = [("krishna@example.com", "Krishna", "org_admin"), ("sender@example.com", "Demo Sender", "sender"),
              ("auditor@example.com", "Demo Auditor", "auditor"), ("templates@example.com", "Template Manager", "template_manager")]
    for email, name, role in people:
        if not db.query(User).filter_by(email=email).first():
            db.add(User(org_id=org.id, email=email, full_name=name, role=role, password_hash=hash_password(password), email_verified=True, password_changed_at=now()))
    db.commit()


if __name__ == "__main__":
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if "--demo" in sys.argv:
        pw = os.environ.get("DEMO_PASSWORD")
        if not pw:
            sys.exit("Set DEMO_PASSWORD (min 12 chars) to create demo users")
        demo(db, pw)
        print("Demo users: krishna@example.com, sender@example.com, auditor@example.com, templates@example.com (password = $DEMO_PASSWORD)")
    print("Seed complete")
