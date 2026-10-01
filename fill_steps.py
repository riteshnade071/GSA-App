"""
Run:  python fill_steps.py
1) Prints EVERYTHING in the database this script is connected to (so you can see what the app really reads).
2) Fills English + Hindi apply-steps for the central NSP post-matric schemes (PMS-SC / PMS-ST / PMS-OBC),
   whatever their exact name is, but ONLY where steps are still empty. Your own edits are never overwritten.
Anything else (e.g. NMMS) is listed as 'needs steps' — add those in the admin panel; steps differ per scheme and must come from the official page.
"""
from sqlalchemy import inspect, text
from app.database import SessionLocal, engine, Base
from app.models.core import Opportunity
from seed_scholarships import nsp_steps, nsp_steps_hi, DOCS

Base.metadata.create_all(bind=engine)
for _col in ("application_steps", "application_steps_hi"):
    if _col not in [c["name"] for c in inspect(engine).get_columns("opportunities")]:
        with engine.begin() as c:
            c.execute(text(f"ALTER TABLE opportunities ADD COLUMN {_col} JSON"))

db = SessionLocal()
print("Connected to database host:", engine.url.host, "\n")
KEYS = ("PMS-SC", "PMS-ST", "PMS-OBC")
for o in db.query(Opportunity).order_by(Opportunity.name).all():
    note = ""
    nationwide = not (o.state or "").strip()
    if nationwide and any(k in (o.name or "").upper() for k in KEYS):
        if not o.application_steps:
            o.application_steps = nsp_steps(o.name)
            note += " [English steps added]"
        if not o.application_steps_hi:
            o.application_steps_hi = nsp_steps_hi(o.name)
            note += " [Hindi steps added]"
        if not o.required_documents:
            o.required_documents = DOCS
    elif not o.application_steps:
        note = " <-- needs steps (add in admin panel)"
    print(f"- {o.name} | state={o.state or 'ALL INDIA'} | active={o.is_active} | steps={len(o.application_steps or [])} hi={len(o.application_steps_hi or [])}{note}")
db.commit()
db.close()
