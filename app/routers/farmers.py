"""
Farmers section — public, read-only API. No login needed.

Farmer schemes are rows of the existing `opportunities` table with category = "farmer_scheme", so the admin
page, the Verify button, archive/unarchive and check_freshness.py all work for them unchanged.
Add or update schemes in data/farmers/*.json and run seed_farmers.py (or use admin.html).
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import Opportunity

router = APIRouter(prefix="/farmers", tags=["Farmers"])

CATEGORY = "farmer_scheme"

SUB_CATEGORIES = {
    "crop_insurance": "Crop insurance",
    "irrigation": "Irrigation",
    "solar_pump": "Solar pumps",
    "equipment": "Farm equipment subsidy",
    "financial": "Financial assistance",
    "loans": "Loans & credit",
    "other": "Other benefits",
}

ELIGIBILITY_GROUPS = {
    "any_farmer": "Any farmer",
    "small_marginal": "Small / marginal farmer",
    "landowner": "Owns cultivable land",
    "tenant": "Tenant / sharecropper",
    "landless": "Landless agricultural family",
    "sc_st": "SC / ST farmer",
    "women": "Woman farmer",
    "fpo_coop": "FPO / cooperative / group",
}


def _fmt(d):
    return d.strftime("%d %b %Y") if d else None


def _base_query(db: Session):
    return db.query(Opportunity).filter(
        Opportunity.category == CATEGORY,
        Opportunity.is_active == True,  # noqa: E712
        Opportunity.verification_status != "ARCHIVED",
    )


def _out(o: Opportunity) -> dict:
    now = datetime.utcnow()
    return {
        "id": o.id, "name": o.name,
        "sub_category": o.sub_category or "other",
        "sub_category_label": SUB_CATEGORIES.get(o.sub_category or "other", "Other benefits"),
        "state": o.state or None,
        "scope": "state" if o.state else "central",
        "description": o.description, "benefits": o.benefits, "amount_text": o.amount_text,
        "eligibility_text": o.eligibility_text, "tags": o.tags or [],
        "required_documents": o.required_documents or [],
        "application_steps": o.application_steps or [],
        "official_url": o.official_url, "source_organization": o.source_organization,
        "last_verified": _fmt(o.last_verified),
        "source_checked_on": _fmt(o.source_checked_on),
        "verification_status": o.verification_status,
        "verified": o.verification_status == "VERIFIED" and o.last_verified is not None,
        "stale": o.last_verified is None or (now - o.last_verified).days > 45,
    }


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    """Filter options for the page: categories (with counts), the states that have schemes, eligibility groups."""
    rows = _base_query(db).all()
    counts: dict = {}
    states = set()
    for o in rows:
        key = o.sub_category or "other"
        counts[key] = counts.get(key, 0) + 1
        if o.state:
            states.add(o.state)
    return {
        "total": len(rows),
        "categories": [{"id": k, "label": v, "count": counts.get(k, 0)} for k, v in SUB_CATEGORIES.items()],
        "states": sorted(states),
        "eligibility_groups": [{"id": k, "label": v} for k, v in ELIGIBILITY_GROUPS.items()],
    }


@router.get("/schemes")
def schemes(state: str | None = None, category: str | None = None, group: str | None = None,
            scope: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    """
    state    -> central (all-India) schemes PLUS that state's schemes
    scope    -> "central" (only all-India) or "state" (only state-specific; combine with state=)
    category -> one of SUB_CATEGORIES
    group    -> who you are; shows schemes open to that group and schemes open to any farmer
    q        -> free-text search over name, description, benefits, eligibility, source
    """
    query = _base_query(db)
    if scope == "central":
        query = query.filter(or_(Opportunity.state.is_(None), Opportunity.state == ""))
    elif scope == "state":
        query = query.filter(Opportunity.state.isnot(None), Opportunity.state != "")
        if state:
            query = query.filter(func.lower(Opportunity.state) == state.lower())
    elif state:
        query = query.filter(or_(Opportunity.state.is_(None), Opportunity.state == "",
                                 func.lower(Opportunity.state) == state.lower()))
    if category:
        query = query.filter(Opportunity.sub_category == category)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.filter(or_(*[func.lower(col).like(like) for col in (
            Opportunity.name, Opportunity.description, Opportunity.benefits,
            Opportunity.eligibility_text, Opportunity.source_organization, Opportunity.amount_text)]))
    items = query.order_by(Opportunity.name).all()
    if group:  # tags live in a JSON column; filter in Python so it behaves the same on every database
        items = [o for o in items if group in (o.tags or []) or "any_farmer" in (o.tags or [])]
    # state-specific schemes first when a state is chosen, then central ones; alphabetical inside each
    items.sort(key=lambda o: (0 if (state and o.state and o.state.lower() == state.lower()) else 1, o.name))
    return [_out(o) for o in items]
