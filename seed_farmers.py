"""
Loader for the Farmers section.   (seed_all.py is for scholarships and is not touched by this file.)

    python seed_farmers.py            -> insert new schemes, fill blanks, never overwrite your admin edits
    python seed_farmers.py --update   -> make the database match data/farmers/*.json; a scheme whose content changed
                                         goes back to NEEDS_REVIEW (press Verify in admin.html after you re-check it)

Data lives in data/farmers/*.json, one file per scope (central.json, maharashtra.json, gujarat.json ...).
To add a state: create data/farmers/<state>.json in the same format and run this script. No code change, no redeploy.
Files starting with "_" (like _queue.md) are notes and are never loaded.

Entry fields
  name, sub_category (crop_insurance | irrigation | solar_pump | equipment | financial | loans | other),
  state (null = all India), description, benefits, amount (short line for the card), eligibility_text,
  tags (any_farmer | small_marginal | landowner | tenant | landless | sc_st | women | fpo_coop),
  required_documents[], steps[] (ordered), official_url, source_organization,
  checked_on ("YYYY-MM-DD": the day the OFFICIAL source was read), aliases[] (optional older names)

Every scheme lands as NEEDS_REVIEW. "Last verified" on the site only appears after an admin presses Verify.
"""
import sys
from app.database import SessionLocal, Base, engine
from app.migrate import ensure_columns
from app.services.farmer_loader import run

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    db = SessionLocal()
    print("Database host:", engine.url.host)
    counts = run(db, update="--update" in sys.argv)
    db.close()
    print("\nSummary:", counts)
