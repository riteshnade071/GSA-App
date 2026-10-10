from sqlalchemy import text, inspect
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.models import core  # noqa: F401 - registers models
from app.routers import auth, profile, opportunities, notices, farmers, careers
from app.database import SessionLocal
from app.migrate import ensure_columns
from app import mailer
from app.services.eligibility_service import expire_past_deadlines

app = FastAPI(title="OpportunityHub", version="0.1.0",
              description="Government benefits, scholarships, careers and study-abroad — in one place.")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])



@app.middleware("http")
async def no_private_caching(request, call_next):
    """Private answers (profile, matches, saved list, auth) must never be kept by a browser or a shared computer's cache."""
    response = await call_next(request)
    public = request.method == "GET" and (request.url.path in ("/", "/opportunities/browse") or request.url.path.startswith("/notices") or request.url.path.startswith("/farmers") or request.url.path.startswith("/careers"))
    if not public:
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(opportunities.router)
app.include_router(notices.router)
app.include_router(farmers.router)
app.include_router(careers.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    # create_all never alters existing tables, so add new columns here (idempotent).
    ensure_columns()
    for problem in mailer.status()["problems"]:
        print(f"[EMAIL SETUP WARNING] {problem}", flush=True)
    db = SessionLocal()
    try:
        expire_past_deadlines(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {"status": "ok", "message": "OpportunityHub API running"}
