from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    name: str
    phone: str
    password: str


class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    has_profile: bool = False
    is_admin: bool = False


class ProfileIn(BaseModel):
    country: Optional[str] = "IN"
    state: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    education_level: Optional[str] = None
    marks_percent: Optional[float] = None
    course_stream: Optional[str] = None
    family_income: Optional[int] = None
    category: Optional[str] = None
    is_disabled: bool = False
    target_countries: Optional[List[str]] = None
    interests: Optional[List[str]] = None


class ProfileOut(ProfileIn):
    id: str

    class Config:
        from_attributes = True


class OpportunityIn(BaseModel):
    name: str
    category: str
    country: Optional[str] = "IN"
    state: Optional[str] = None
    description: Optional[str] = None
    benefits: Optional[str] = None
    required_documents: Optional[List[str]] = None
    deadline: Optional[datetime] = None
    eligibility_rules: Optional[Dict[str, Any]] = None
    official_url: str
    source_organization: Optional[str] = None
    last_verified: Optional[datetime] = None
    verification_status: str = "NEEDS_REVIEW"


class SaveOpportunityIn(BaseModel):
    opportunity_id: str
    status: Optional[str] = "saved"
    note: Optional[str] = None
