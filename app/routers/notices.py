from datetime import datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import Notice, Opportunity, User
from app.schemas.schemas import NoticeIn
from app.auth import get_current_user

router = APIRouter(prefix="/notices", tags=["Notices"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user


def _out(n: Notice, db: Session) -> dict:
    scheme = db.query(Opportunity.name).filter(Opportunity.id == n.opportunity_id).scalar() if n.opportunity_id else None
    return {
        "id": n.id, "title": n.title, "summary": n.summary, "url": n.url, "source_name": n.source_name,
        "state": n.state, "scheme": scheme, "opportunity_id": n.opportunity_id,
        "published_on": n.published_on.strftime("%d %b %Y") if n.published_on else None,
        "expires_on": n.expires_on.isoformat() if n.expires_on else None,
        "is_published": n.is_published, "auto_found": n.auto_found,
    }


@router.get("")
def public_notices(state: str | None = None, db: Session = Depends(get_db)):
    """Public. Published, not-expired notices: all-India ones plus the given state's. Newest first."""
    today = datetime.combine(datetime.utcnow().date(), time.min)
    q = db.query(Notice).filter(
        Notice.is_published == True,  # noqa: E712
        or_(and_(Notice.expires_on.isnot(None), Notice.expires_on >= today),
            and_(Notice.expires_on.is_(None), Notice.published_on >= datetime.utcnow() - timedelta(days=90))),
    )
    if state:
        q = q.filter(or_(Notice.state.is_(None), Notice.state == "", func.lower(Notice.state) == state.lower()))
    else:
        q = q.filter(or_(Notice.state.is_(None), Notice.state == ""))
    return [_out(n, db) for n in q.order_by(Notice.published_on.desc()).limit(15).all()]


@router.get("/admin/list")
def admin_list(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [_out(n, db) for n in db.query(Notice).order_by(Notice.created_at.desc()).limit(200).all()]


@router.post("/admin/add")
def admin_add(payload: NoticeIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    n = Notice(**payload.model_dump(), auto_found=False, published_on=datetime.utcnow())
    db.add(n); db.commit(); db.refresh(n)
    return _out(n, db)


@router.put("/admin/{notice_id}")
def admin_edit(notice_id: str, payload: NoticeIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    n = db.query(Notice).filter(Notice.id == notice_id).first()
    if not n:
        raise HTTPException(404, "Notice not found")
    for k, v in payload.model_dump().items():
        setattr(n, k, v)
    db.commit()
    return _out(n, db)


@router.post("/admin/{notice_id}/toggle-publish")
def admin_toggle(notice_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    n = db.query(Notice).filter(Notice.id == notice_id).first()
    if not n:
        raise HTTPException(404, "Notice not found")
    n.is_published = not n.is_published
    if n.is_published:
        n.published_on = datetime.utcnow()    # shows as new when approved
    db.commit()
    return {"is_published": n.is_published}


class BulkIn(BaseModel):
    action: str   # publish_drafts | delete_drafts


@router.post("/admin/bulk")
def admin_bulk(payload: BulkIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """One click for the whole pile of auto-found drafts."""
    q = db.query(Notice).filter(Notice.auto_found == True, Notice.is_published == False)  # noqa: E712
    if payload.action == "publish_drafts":
        n = q.update({"is_published": True, "published_on": datetime.utcnow()}, synchronize_session=False)
    elif payload.action == "delete_drafts":
        n = q.delete(synchronize_session=False)
    else:
        raise HTTPException(400, "Unknown action")
    db.commit()
    return {"count": n}


@router.delete("/admin/{notice_id}")
def admin_delete(notice_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    n = db.query(Notice).filter(Notice.id == notice_id).first()
    if not n:
        raise HTTPException(404, "Notice not found")
    db.delete(n); db.commit()
    return {"deleted": True}
