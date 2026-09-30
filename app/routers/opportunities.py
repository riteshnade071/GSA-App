from datetime import datetime
from sqlalchemy import or_, func
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import Profile, Opportunity, SavedOpportunity, User
from app.schemas.schemas import OpportunityIn, SaveOpportunityIn
from app.services.eligibility_service import find_matches
from app.auth import get_current_user

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


@router.get("/matches")
def my_matches(category: str | None = None, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    """The core screen: everything this user may be eligible for, best fit first."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(400, "Fill in your profile first so we can match opportunities to you.")
    return {"matches": find_matches(db, profile, category=category)}


@router.get("/browse")
def browse(category: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    """Public browse — no login, no matching. Lets people see value before signing up."""
    query = db.query(Opportunity).filter(Opportunity.is_active == True)  # noqa: E712
    if category:
        query = query.filter(Opportunity.category == category)
    if state:  # nationwide + that state's own scholarships
        query = query.filter(or_(Opportunity.state.is_(None), Opportunity.state == "",
                                 func.lower(Opportunity.state) == state.lower()))
    return [{
        "id": o.id, "name": o.name, "category": o.category, "state": o.state,
        "application_steps": o.application_steps or [],
        "description": o.description, "benefits": o.benefits,
        "deadline": o.deadline.strftime("%d %b %Y") if o.deadline else None,
        "official_url": o.official_url, "source_organization": o.source_organization,
        "last_verified": o.last_verified.strftime("%d %b %Y") if o.last_verified else None,
        "verification_status": o.verification_status,
    } for o in query.order_by(Opportunity.name).all()]


@router.post("/save")
def save_opportunity(payload: SaveOpportunityIn, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    existing = db.query(SavedOpportunity).filter(
        SavedOpportunity.user_id == current_user.id,
        SavedOpportunity.opportunity_id == payload.opportunity_id,
    ).first()
    if existing:
        existing.status = payload.status
        existing.note = payload.note
    else:
        db.add(SavedOpportunity(user_id=current_user.id, **payload.model_dump()))
    db.commit()
    return {"saved": True}


@router.get("/saved")
def my_saved(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(SavedOpportunity).filter(SavedOpportunity.user_id == current_user.id).all()
    out = []
    for row in rows:
        opp = db.query(Opportunity).filter(Opportunity.id == row.opportunity_id).first()
        if not opp:
            continue
        out.append({
            "id": opp.id, "name": opp.name, "category": opp.category,
            "status": row.status, "note": row.note,
            "deadline": opp.deadline.strftime("%d %b %Y") if opp.deadline else None,
            "official_url": opp.official_url,
        })
    return out


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
        "application_steps": o.application_steps,
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
    opp.is_active = not opp.is_active
    if not opp.is_active:
        opp.verification_status = "ARCHIVED"
    db.commit()
    return {"is_active": opp.is_active}
