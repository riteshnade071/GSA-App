from datetime import datetime
from sqlalchemy import or_, func
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import Profile, Opportunity, SavedOpportunity, User
from app.schemas.schemas import OpportunityIn, SaveOpportunityIn
from app.services.eligibility_service import find_matches, expire_past_deadlines
from app.auth import get_current_user

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


@router.get("/matches")
def my_matches(category: str | None = None, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    """The core screen: everything this user may be eligible for, best fit first."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(400, "Fill in your profile first so we can match opportunities to you.")
    matches = find_matches(db, profile, category=category)
    saved = {r.opportunity_id: r.status for r in db.query(SavedOpportunity).filter(SavedOpportunity.user_id == current_user.id)}
    for m in matches:
        m["saved_status"] = saved.get(m["id"])
    return {"matches": matches}


@router.get("/browse")
def browse(category: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    """Public browse — no login, no matching. Lets people see value before signing up."""
    expire_past_deadlines(db)
    query = db.query(Opportunity).filter(Opportunity.is_active == True)  # noqa: E712
    if category:
        query = query.filter(Opportunity.category == category)
    if state:  # nationwide + that state's own scholarships
        query = query.filter(or_(Opportunity.state.is_(None), Opportunity.state == "",
                                 func.lower(Opportunity.state) == state.lower()))
    return [{
        "id": o.id, "name": o.name, "category": o.category, "state": o.state,
        "application_steps": o.application_steps or [], "application_steps_hi": o.application_steps_hi or [], "amount_text": o.amount_text,
        "description": o.description, "benefits": o.benefits,
        "deadline": o.deadline.strftime("%d %b %Y") if o.deadline else None,
        "official_url": o.official_url, "source_organization": o.source_organization,
        "last_verified": o.last_verified.strftime("%d %b %Y") if o.last_verified else None,
        "verification_status": o.verification_status,
    } for o in query.order_by(Opportunity.name).all()]


STATUSES = {"saved", "applied", "under_review", "approved", "received", "rejected"}


@router.post("/save")
def save_opportunity(payload: SaveOpportunityIn, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    """Create or update the student's own tracking row. Only the fields actually sent are changed."""
    data = payload.model_dump(exclude_unset=True)
    opp_id = data.pop("opportunity_id")
    if data.get("status") and data["status"] not in STATUSES:
        raise HTTPException(400, "Unknown status")
    if not db.query(Opportunity.id).filter(Opportunity.id == opp_id).first():
        raise HTTPException(404, "Opportunity not found")
    row = db.query(SavedOpportunity).filter(SavedOpportunity.user_id == current_user.id,
                                            SavedOpportunity.opportunity_id == opp_id).first()
    if row:
        for k, v in data.items():
            setattr(row, k, v)
    else:
        row = SavedOpportunity(user_id=current_user.id, opportunity_id=opp_id, **data)
        db.add(row)
    if row.status in ("applied", "under_review", "approved", "received") and not row.applied_on:
        row.applied_on = datetime.utcnow()
    db.commit()
    return {"saved": True, "status": row.status}


@router.get("/saved")
def my_saved(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = datetime.utcnow()
    out = []
    for row in db.query(SavedOpportunity).filter(SavedOpportunity.user_id == current_user.id).all():
        opp = db.query(Opportunity).filter(Opportunity.id == row.opportunity_id).first()
        if not opp:
            continue
        out.append({
            "id": opp.id, "name": opp.name, "category": opp.category, "state": opp.state,
            "status": row.status, "note": row.note, "application_id": row.application_id,
            "applied_on": row.applied_on.strftime("%d %b %Y") if row.applied_on else None,
            "updated_days": (now - row.updated_at).days if row.updated_at else None,
            "deadline": opp.deadline.strftime("%d %b %Y") if opp.deadline else None,
            "days_left": (opp.deadline.date() - now.date()).days if opp.deadline else None,
            "expired": not opp.is_active,
            "official_url": opp.official_url,
        })
    return out


@router.delete("/saved/{opportunity_id}")
def remove_saved(opportunity_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.query(SavedOpportunity).filter(SavedOpportunity.user_id == current_user.id,
                                      SavedOpportunity.opportunity_id == opportunity_id).delete()
    db.commit()
    return {"removed": True}


@router.post("/admin/add")
def admin_add(payload: OpportunityIn, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    """Admin-only. This is how new opportunities and their rules get in — no redeploy needed."""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    opp = Opportunity(**payload.model_dump())
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return {"id": opp.id, "name": opp.name}


@router.get("/admin/list")
def admin_list(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Everything, including archived/unverified — the admin needs to see it all to manage it."""
    expire_past_deadlines(db)
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    rows = db.query(Opportunity).order_by(Opportunity.created_at.desc()).all()
    return [{
        "id": o.id, "name": o.name, "category": o.category, "country": o.country, "state": o.state,
        "description": o.description, "benefits": o.benefits, "required_documents": o.required_documents,
        "deadline": o.deadline.isoformat() if o.deadline else None,
        "eligibility_rules": o.eligibility_rules,
        "official_url": o.official_url, "source_organization": o.source_organization,
        "last_verified": o.last_verified.strftime("%d %b %Y") if o.last_verified else None,
        "verification_status": o.verification_status, "is_active": o.is_active,
        "application_steps": o.application_steps, "application_steps_hi": o.application_steps_hi, "state_basis": o.state_basis, "amount_text": o.amount_text,
    } for o in rows]


@router.put("/admin/{opportunity_id}")
def admin_edit(opportunity_id: str, payload: OpportunityIn, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    for field, value in payload.model_dump().items():
        setattr(opp, field, value)
    if opp.deadline and opp.deadline.date() >= datetime.utcnow().date() and opp.verification_status in ("EXPIRED", "ARCHIVED"):
        opp.verification_status = "NEEDS_REVIEW"   # new cycle: must be re-verified before it counts as verified
        opp.is_active = True
    db.commit()
    return {"id": opp.id, "name": opp.name}


@router.post("/admin/{opportunity_id}/verify")
def admin_verify(opportunity_id: str, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """One tap to mark 'I just checked the official site, this is still accurate today.'"""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    opp.last_verified = datetime.utcnow()
    opp.verification_status = "VERIFIED"
    db.commit()
    return {"verified": True}


@router.post("/admin/{opportunity_id}/toggle-active")
def admin_toggle_active(opportunity_id: str, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    """Archive/unarchive instead of deleting — students may have already saved it."""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    if not opp.is_active and opp.deadline and opp.deadline.date() < datetime.utcnow().date():
        raise HTTPException(400, "The deadline has passed. Edit the deadline first, then it comes back automatically.")
    opp.is_active = not opp.is_active
    opp.verification_status = "ARCHIVED" if not opp.is_active else "NEEDS_REVIEW"
    db.commit()
    return {"is_active": opp.is_active}
