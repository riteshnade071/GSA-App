import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Profile(Base):
    """
    Everything the eligibility engine matches against. Every field is optional —
    a user who has filled in only half their profile still gets matches, with the
    unknown conditions clearly flagged, rather than being silently excluded.
    """
    __tablename__ = "profiles"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    country = Column(String)           # "IN"
    state = Column(String)             # home state (domicile), e.g. "Maharashtra"
    study_state = Column(String)       # state where the college is (can differ from home state)
    age = Column(Integer)
    gender = Column(String)            # male / female / other
    education_level = Column(String)   # 10th / 12th / diploma / bachelors / masters
    marks_percent = Column(Float)
    course_stream = Column(String)     # science / commerce / arts / engineering
    family_income = Column(Integer)    # annual, INR
    category = Column(String)          # general / obc / sc / st / ews / minority
    is_disabled = Column(Boolean, default=False)
    target_countries = Column(JSON)    # ["JP", "DE"]
    interests = Column(JSON)           # ["technology", "design"]
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Opportunity(Base):
    """
    One row per scheme / scholarship / program. eligibility_rules is JSON data,
    NOT code — that's what lets an admin add a scholarship with new conditions
    without anyone redeploying the backend.
    """
    __tablename__ = "opportunities"
    id = Column(String(36), primary_key=True, default=gen_uuid)

    name = Column(String, nullable=False)
    category = Column(String, nullable=False)   # scholarship / govt_benefit / study_abroad
    country = Column(String)                    # who it's for
    state = Column(String)                      # null = nationwide
    description = Column(Text)
    benefits = Column(Text)
    required_documents = Column(JSON)
    state_basis = Column(String, default="domicile")   # what `state` is checked against: domicile | institute | both
    amount_text = Column(String)                # short "how much" line shown on the card
    application_steps_hi = Column(JSON)         # same steps in Hindi, same order/length as application_steps
    application_steps = Column(JSON)            # ordered list of strings: what to do after clicking Apply
    deadline = Column(DateTime, nullable=True)
    eligibility_rules = Column(JSON)            # see eligibility_service.py

    # Trust layer — the plan's most important pillar
    official_url = Column(String, nullable=False)
    source_organization = Column(String)
    last_verified = Column(DateTime)
    verification_status = Column(String, default="NEEDS_REVIEW")

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SavedOpportunity(Base):
    __tablename__ = "saved_opportunities"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id"), nullable=False)
    status = Column(String, default="saved")
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notice(Base):
    """
    A government announcement related to scholarships (new window opened, date extended, new scheme, correction...).
    Nothing is shown to students until an admin publishes it — auto-found items arrive as drafts.
    """
    __tablename__ = "notices"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    summary = Column(Text)
    url = Column(String, nullable=False)                 # link to the official notice
    source_name = Column(String)                         # e.g. "scholarships.gov.in"
    state = Column(String)                               # null = all India
    opportunity_id = Column(String(36), ForeignKey("opportunities.id"), nullable=True)
    published_on = Column(DateTime, default=datetime.utcnow)
    expires_on = Column(DateTime, nullable=True)         # hidden after this day; if empty, hidden 90 days after published_on
    is_published = Column(Boolean, default=False)
    auto_found = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
