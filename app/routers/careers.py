"""
Career Guidance section — public API, no login needed. Content comes from data/careers/*.json (see career_service.py).
Scholarship suggestions are read from the existing scholarships in the database; nothing is stored about the student.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import Opportunity
from app.services import career_service as cs

router = APIRouter(prefix="/careers", tags=["Careers"])


class RecommendIn(BaseModel):
    stage: str
    stream: str | None = None
    interests: list[str] = []
    skills: list[str] = []
    budget: str | None = "medium"
    goal: str | None = None
    state: str | None = None


def _scholarships_for(db: Session, path: dict, state: str | None, limit: int = 3) -> list:
    """Active scholarships whose name or description mentions one of the path's keywords (nationwide + the student's state)."""
    kws = [k.lower() for k in path.get("scholarship_keywords", []) if k]
    if not kws:
        return []
    q = db.query(Opportunity).filter(Opportunity.is_active == True, Opportunity.category == "scholarship")  # noqa: E712
    if state:
        q = q.filter(or_(Opportunity.state.is_(None), Opportunity.state == "", func.lower(Opportunity.state) == state.lower()))
    else:
        q = q.filter(or_(Opportunity.state.is_(None), Opportunity.state == ""))
    out = []
    for o in q.order_by(Opportunity.name).all():
        text = f"{o.name} {o.description or ''}".lower()
        if any(k in text for k in kws):
            out.append({"id": o.id, "name": o.name, "state": o.state, "amount_text": o.amount_text, "official_url": o.official_url})
        if len(out) >= limit:
            break
    return out


@router.get("/meta")
def meta():
    d = cs.load()
    counts: dict = {}
    for p in d["paths"]:
        counts[p["type"]] = counts.get(p["type"], 0) + 1
    return {
        "stages": [{"id": k, "title": v["title"]} for k, v in d["guides"]["stages"].items()],
        "types": [{"id": k, "label": v, "count": counts.get(k, 0)} for k, v in cs.TYPE_LABELS.items() if counts.get(k)],
        "total_paths": len(d["paths"]),
        "disclaimer": d["guides"]["disclaimer"],
        "study_abroad_checklist": d["guides"]["study_abroad_checklist"],
    }


@router.get("/questionnaire")
def questionnaire():
    return cs.load()["questionnaire"]


@router.get("/guide/{stage}")
def guide(stage: str, stream: str | None = None):
    g = cs.stage_guide(stage, stream)
    if not g:
        raise HTTPException(404, "Unknown stage")
    return g


@router.get("/paths")
def paths(type: str | None = None, stage: str | None = None, q: str | None = None):
    items = cs.load()["paths"]
    if type:
        items = [p for p in items if p["type"] == type]
    if stage:
        items = [p for p in items if stage in p["stages"]]
    if q and q.strip():
        needle = q.strip().lower()
        items = [p for p in items if needle in (p["title"] + " " + p["summary"] + " " + " ".join(p.get("courses", []))).lower()]
    return [cs.summary(p) for p in items]


@router.get("/paths/{path_id}")
def path_detail(path_id: str, state: str | None = None, db: Session = Depends(get_db)):
    p = cs.load()["by_id"].get(path_id)
    if not p:
        raise HTTPException(404, "Career path not found")
    out = cs.full(p)
    out["scholarships"] = _scholarships_for(db, p, state)
    return out


@router.post("/recommend")
def recommend(payload: RecommendIn, db: Session = Depends(get_db)):
    if payload.stage not in cs.load()["guides"]["stages"]:
        raise HTTPException(400, "Unknown stage")
    results = cs.recommend(payload.model_dump())
    for r in results:
        r["scholarships"] = _scholarships_for(db, r, payload.state)
    return {"recommendations": results, "disclaimer": cs.load()["guides"]["disclaimer"]}
