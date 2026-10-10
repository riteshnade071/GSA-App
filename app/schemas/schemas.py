from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str
    phone: str
    password: str = Field(min_length=6)
    verification_token: Optional[str] = None     # from /auth/otp/verify


class OtpRequest(BaseModel):
    phone: str
    purpose: str = "signup"                      # signup | reset
    email: str                                   # the code is sent here


class OtpVerify(BaseModel):
    phone: str
    code: str
    email: str


class ResetPasswordRequest(BaseModel):
    phone: str
    code: str
    new_password: str = Field(min_length=6)
    email: str


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


class AddEmailRequest(BaseModel):
    email: str


class AddEmailVerify(BaseModel):
    email: str
    code: str


class ProfileIn(BaseModel):
    country: Optional[str] = "IN"
    state: Optional[str] = None
    study_state: Optional[str] = None
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
    application_steps: Optional[List[str]] = None
    application_steps_hi: Optional[List[str]] = None
    state_basis: Optional[str] = "domicile"
    amount_text: Optional[str] = None
    deadline: Optional[datetime] = None
    eligibility_rules: Optional[Dict[str, Any]] = None
    official_url: str
    source_organization: Optional[str] = None
    last_verified: Optional[datetime] = None
    verification_status: str = "NEEDS_REVIEW"
    # Farmers section (optional; scholarships leave these out)
    sub_category: Optional[str] = None
    eligibility_text: Optional[str] = None
    tags: Optional[List[str]] = None
    source_checked_on: Optional[datetime] = None


class NoticeIn(BaseModel):
    title: str
    summary: Optional[str] = None
    url: str
    source_name: Optional[str] = None
    state: Optional[str] = None
    opportunity_id: Optional[str] = None
    expires_on: Optional[datetime] = None
    is_published: bool = True


class SaveOpportunityIn(BaseModel):
    opportunity_id: str
    status: Optional[str] = "saved"
    note: Optional[str] = None
    application_id: Optional[str] = None
