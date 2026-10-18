"""
Loads data/farmers/*.json into the database (used by seed_farmers.py and by the admin "Load farmer schemes" button).
Lives inside the app package so it can always be imported by the running server.
Data format: see the notes at the top of seed_farmers.py.
"""
import glob, json, os
from datetime import datetime
from app.models.core import Opportunity

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # project root
SUB_CATEGORIES = {"crop_insurance", "irrigation", "solar_pump", "equipment", "financial", "loans", "other"}
TAGS = {"any_farmer", "small_marginal", "landowner", "tenant", "landless", "sc_st", "women", "fpo_coop"}


def load():
    entries = []
    for f in sorted(glob.glob(os.path.join(HERE, "data", "farmers", "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        entries += json.load(open(f, encoding="utf-8"))
    for e in entries:
        for k in ("name", "sub_category", "official_url", "steps", "checked_on", "eligibility_text"):
            assert e.get(k), f"{e.get('name')}: missing {k}"
        assert e["sub_category"] in SUB_CATEGORIES, f"{e['name']}: unknown sub_category {e['sub_category']}"
        assert set(e.get("tags", [])) <= TAGS, f"{e['name']}: unknown tag in {e.get('tags')}"
        assert e["official_url"].startswith("https://"), f"{e['name']}: official_url must start with https://"
        datetime.strptime(e["checked_on"], "%Y-%m-%d")
    names = [e["name"] for e in entries]
    assert len(names) == len(set(names)), "duplicate scheme name in data/farmers"
    return entries


def values(e):
    return dict(
        name=e["name"], category="farmer_scheme", sub_category=e["sub_category"], country="IN", state=e.get("state"),
        description=e.get("description"), benefits=e.get("benefits"), amount_text=e.get("amount"),
        eligibility_text=e.get("eligibility_text"), tags=e.get("tags", []),
        required_documents=e.get("required_documents"), application_steps=e["steps"],
        official_url=e["official_url"], source_organization=e.get("source_organization"),
        source_checked_on=datetime.strptime(e["checked_on"], "%Y-%m-%d"),
        eligibility_rules={},   # farmer schemes are not matched against a student profile
    )


def run(db, update=False, log=print):
    """Insert / update farmer schemes from data/farmers/*.json. Used by this script and by the admin button."""
    entries = load()
    counts = {"inserted": 0, "updated": 0, "unchanged": 0, "filled": 0}
    for e in entries:
        v = values(e)
        row = db.query(Opportunity).filter(Opportunity.category == "farmer_scheme",
                                           Opportunity.name.in_([e["name"]] + e.get("aliases", []))).first()
        if row is None:
            db.add(Opportunity(verification_status="NEEDS_REVIEW", **v)); status = "inserted"
        elif update:
            content = {k: val for k, val in v.items() if k != "source_checked_on"}
            changed = [k for k, val in content.items() if getattr(row, k) != val]
            if changed:
                for k in changed: setattr(row, k, v[k])
                row.source_checked_on = v["source_checked_on"]
                row.verification_status, row.last_verified = "NEEDS_REVIEW", None
                status = "updated"
            else:
                if row.source_checked_on != v["source_checked_on"]:
                    row.source_checked_on = v["source_checked_on"]
                status = "unchanged"
        else:
            filled = False
            for k in ("application_steps", "required_documents", "eligibility_text", "tags", "sub_category", "source_checked_on"):
                if not getattr(row, k): setattr(row, k, v[k]); filled = True
            status = "filled" if filled else "unchanged"
        counts[status] += 1
        log(f"{status:9} {('[' + (e.get('state') or 'ALL INDIA') + ']'):15} {e['name']}")
    db.commit()
    return counts


