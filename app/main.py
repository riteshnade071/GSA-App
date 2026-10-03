from sqlalchemy import text, inspect
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.models import core  # noqa: F401 - registers models
from app.routers import auth, profile, opportunities
from app.database import SessionLocal
from app.services.eligibility_service import expire_past_deadlines

app = FastAPI(title="OpportunityHub", version="0.1.0",
              description="Government benefits, scholarships, careers and study-abroad — in one place.")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(opportunities.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    # create_all never alters existing tables, so add new columns here (idempotent).
    cols = [c["name"] for c in inspect(engine).get_columns("opportunities")]
    for col in ("application_steps", "application_steps_hi"):
        if col not in cols:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE opportunities ADD COLUMN {col} JSON"))
    db = SessionLocal()
    try:
        expire_past_deadlines(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {"status": "ok", "message": "OpportunityHub API running"}
