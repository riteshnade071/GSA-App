"""
One loader for ALL scholarship data.   python seed_all.py            -> insert new ones, fill blanks, never touch your admin edits
                                       python seed_all.py --update   -> overwrite rows with what is in data/*.json (rows whose content CHANGED go back to NEEDS_REVIEW)

Data lives in data/*.json (one file per scope: central.json, maharashtra.json, ... add karnataka.json etc.). No code change is ever needed to add schemes.
data/steps.json holds the shared English + Hindi "how to apply" templates; "{scheme}" is replaced by the scheme name.
Entry fields: name, aliases(optional), state(null = all India), description, benefits, source_organization, official_url,
              deadline("YYYY-MM-DD" or null), amount (short line for the card), state_basis (domicile|institute|both), required_documents[], eligibility_rules{}, steps("nsp"/"mahadbt"), steps_name(optional)
"""
import glob, json, os, sys
from datetime import datetime
from sqlalchemy import inspect, text
from app.database import SessionLocal, Base, engine
from app.models.core import Opportunity
from app.migrate import ensure_columns

HERE = os.path.dirname(os.path.abspath(__file__))
UPDATE = "--update" in sys.argv


def load():
    read = lambda p: json.load(open(p, encoding="utf-8"))
    steps = read(os.path.join(HERE, "data", "steps.json"))
    entries = []
    for f in sorted(glob.glob(os.path.join(HERE, "data", "*.json"))):
        if os.path.basename(f) not in ("steps.json", "sources.json"):   # these two are not scheme lists
            entries += read(f)
    for e in entries:
        for k in ("name", "official_url", "eligibility_rules", "steps"):
            assert e.get(k) is not None, f"{e.get('name')}: missing {k}"
        assert e["steps"] in steps, f"{e['name']}: unknown steps template {e['steps']}"
    return steps, entries


def values(e, steps):
    label = e.get("steps_name", e["name"])
    t = steps[e["steps"]]
    return dict(
        name=e["name"], category=e.get("category", "scholarship"), country="IN", state=e.get("state"),
        description=e.get("description"), benefits=e.get("benefits"), required_documents=e.get("required_documents"),
        deadline=datetime.strptime(e["deadline"], "%Y-%m-%d") if e.get("deadline") else None,
        state_basis=e.get("state_basis", "domicile"), amount_text=e.get("amount"),
        eligibility_rules=e["eligibility_rules"], official_url=e["official_url"], source_organization=e.get("source_organization"),
        application_steps=[s.replace("{scheme}", label) for s in t["en"]],
        application_steps_hi=[s.replace("{scheme}", label) for s in t["hi"]],
    )


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    steps, entries = load()
    db = SessionLocal()
    print("Database host:", engine.url.host)
    counts = {"inserted": 0, "updated": 0, "unchanged": 0, "filled": 0}
    for e in entries:
        v = values(e, steps)
        row = db.query(Opportunity).filter(Opportunity.name.in_([e["name"]] + e.get("aliases", []))).first()
        if row is None:
            db.add(Opportunity(verification_status="NEEDS_REVIEW", **v)); status = "inserted"
        elif UPDATE:
            changed = [k for k, val in v.items() if getattr(row, k) != val]
            if changed:
                for k in changed: setattr(row, k, v[k])
                row.verification_status, row.last_verified = "NEEDS_REVIEW", None
                status = "updated"
            else:
                status = "unchanged"
        else:
            filled = False
            for k in ("application_steps", "application_steps_hi", "required_documents"):
                if not getattr(row, k): setattr(row, k, v[k]); filled = True
            status = "filled" if filled else "unchanged"
        counts[status] += 1
        print(f"{status:9} {('[' + (e.get('state') or 'ALL INDIA') + ']'):15} {e['name']}")
    db.commit(); db.close()
    print("\nSummary:", counts)
