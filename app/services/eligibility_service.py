"""
Eligibility engine.

Rules live in the database as JSON, never as Python code, so an admin can add a
scholarship with brand-new conditions without a developer redeploying anything.

Rule format — a dict of {profile_field: {operator: value}}:

    {
      "country":         {"eq":  "IN"},
      "education_level": {"in":  ["12th", "diploma"]},
      "family_income":   {"lte": 300000},
      "age":             {"gte": 17, "lte": 25},
      "marks_percent":   {"gte": 60},
      "category":        {"in":  ["sc", "st", "obc"]}
    }

Every condition returns PASS, FAIL, or UNKNOWN (the user hasn't filled that
field in yet). UNKNOWN is deliberately NOT treated as a failure: a half-filled
profile should still surface opportunities, with the missing pieces shown as
"check this yourself" rather than silently hiding the scholarship.

This is also why we report a match LABEL ("High match") instead of a fake
percentage — we only know what the user told us, and claiming "80% eligible"
about someone's scholarship chances when a rule is unverified is the kind of
thing that destroys trust in a platform like this.
"""
from datetime import datetime, time

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"


def _check_condition(profile_value, operators: dict) -> str:
    if profile_value is None or profile_value == "":
        return UNKNOWN

    for op, expected in operators.items():
        try:
            if op == "eq" and str(profile_value).lower() != str(expected).lower():
                return FAIL
            if op == "neq" and str(profile_value).lower() == str(expected).lower():
                return FAIL
            if op == "in":
                allowed = [str(x).lower() for x in expected]
                if str(profile_value).lower() not in allowed:
                    return FAIL
            if op == "not_in":
                blocked = [str(x).lower() for x in expected]
                if str(profile_value).lower() in blocked:
                    return FAIL
            if op == "gte" and float(profile_value) < float(expected):
                return FAIL
            if op == "lte" and float(profile_value) > float(expected):
                return FAIL
            if op == "gt" and float(profile_value) <= float(expected):
                return FAIL
            if op == "lt" and float(profile_value) >= float(expected):
                return FAIL
            if op == "is_true" and not bool(profile_value):
                return FAIL
        except (ValueError, TypeError):
            # A rule that can't be evaluated against this profile value is
            # treated as unknown, never as a silent pass.
            return UNKNOWN
    return PASS


def evaluate(profile, opportunity) -> dict:
    """
    Returns the match result for one profile against one opportunity:
      {
        "match": "high" | "partial" | "excluded",
        "failed":  [human-readable reasons it doesn't fit],
        "unknown": [profile fields the user still needs to fill in],
        "matched": [conditions that do fit]
      }
    """
    rules = opportunity.eligibility_rules or {}
    failed, unknown, matched = [], [], []

    # Location scope: state empty = nationwide, otherwise only that state's students.
    opp_country = (getattr(opportunity, "country", None) or "").strip()
    user_country = (getattr(profile, "country", None) or "").strip()
    if opp_country and user_country and opp_country.lower() != user_country.lower():
        failed.append(f"only for residents of {opp_country}")
    opp_state = (getattr(opportunity, "state", None) or "").strip()
    if opp_state:
        user_state = (getattr(profile, "state", None) or "").strip()
        if not user_state:
            unknown.append("state")
        elif user_state.lower() != opp_state.lower():
            failed.append(f"only for students of {opp_state}")
        else:
            matched.append(f"state is {opp_state}")

    for field, operators in rules.items():
        value = getattr(profile, field, None)
        result = _check_condition(value, operators)
        label = _describe(field, operators)

        if result == FAIL:
            failed.append(label)
        elif result == UNKNOWN:
            unknown.append(field.replace("_", " "))
        else:
            matched.append(label)

    if failed:
        match = "excluded"
    elif unknown:
        match = "partial"
    else:
        match = "high"

    return {"match": match, "failed": failed, "unknown": unknown, "matched": matched}


def _describe(field: str, operators: dict) -> str:
    """Turns a raw rule into something a student can actually read."""
    pretty_field = field.replace("_", " ")
    parts = []
    for op, val in operators.items():
        if op == "eq":
            parts.append(f"{pretty_field} is {val}")
        elif op == "neq":
            parts.append(f"{pretty_field} is not {val}")
        elif op == "in":
            parts.append(f"{pretty_field} is one of: {', '.join(str(v) for v in val)}")
        elif op == "not_in":
            parts.append(f"{pretty_field} is not: {', '.join(str(v) for v in val)}")
        elif op == "gte":
            parts.append(f"{pretty_field} at least {val}")
        elif op == "lte":
            parts.append(f"{pretty_field} at most {val}")
        elif op == "gt":
            parts.append(f"{pretty_field} above {val}")
        elif op == "lt":
            parts.append(f"{pretty_field} below {val}")
        elif op == "is_true":
            parts.append(f"{pretty_field} required")
    return " and ".join(parts)


def expire_past_deadlines(db) -> int:
    """
    Auto-expiry. Any active opportunity whose deadline DAY has passed is switched off
    (is_active=False, status EXPIRED). The deadline day itself still counts as open.
    Called on startup and lazily on every browse/matches/admin-list request, so it works
    even on hosts that sleep (Render free tier) — no cron job needed.
    """
    from app.models.core import Opportunity
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    n = db.query(Opportunity).filter(
        Opportunity.is_active == True,  # noqa: E712
        Opportunity.deadline.isnot(None),
        Opportunity.deadline < today_start,
    ).update({"is_active": False, "verification_status": "EXPIRED"}, synchronize_session=False)
    if n:
        db.commit()
    return n


def find_matches(db, profile, category=None, include_excluded=False):
    """
    Runs every active opportunity against one profile. High matches first,
    then partial. Excluded ones are dropped unless explicitly asked for —
    an admin reviewing rules wants to see them, a student does not.
    """
    from app.models.core import Opportunity

    query = db.query(Opportunity).filter(
        Opportunity.is_active == True,  # noqa: E712
        Opportunity.verification_status != "ARCHIVED",
    )
    if category:
        query = query.filter(Opportunity.category == category)

    expire_past_deadlines(db)
    results = []
    now = datetime.utcnow()

    for opp in query.all():
        verdict = evaluate(profile, opp)
        if verdict["match"] == "excluded" and not include_excluded:
            continue

        days_left = (opp.deadline.date() - now.date()).days if opp.deadline else None
        # A passed deadline means it isn't an opportunity any more, whatever
        # the eligibility rules say.
        if days_left is not None and days_left < 0:
            continue

        results.append({
            "id": opp.id,
            "name": opp.name,
            "category": opp.category,
            "state": opp.state,
            "scope": "state" if opp.state else "nationwide",
            "application_steps": opp.application_steps or [],
            "application_steps_hi": opp.application_steps_hi or [],
            "description": opp.description,
            "benefits": opp.benefits,
            "required_documents": opp.required_documents or [],
            "deadline": opp.deadline.strftime("%d %b %Y") if opp.deadline else None,
            "days_left": days_left,
            "official_url": opp.official_url,
            "source_organization": opp.source_organization,
            "last_verified": opp.last_verified.strftime("%d %b %Y") if opp.last_verified else None,
            "verification_status": opp.verification_status,
            "match": verdict["match"],
            "matched_conditions": verdict["matched"],
            "unknown_fields": verdict["unknown"],
            "failed_conditions": verdict["failed"],
        })

    order = {"high": 0, "partial": 1, "excluded": 2}
    results.sort(key=lambda r: (order[r["match"]], r["scope"] != "state", r["days_left"] if r["days_left"] is not None else 9999))
    return results
