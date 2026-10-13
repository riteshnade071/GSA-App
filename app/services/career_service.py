"""
Career guidance engine.

All content lives in data/careers/*.json (questionnaire.json, guides.json, paths_*.json). Editing those files is the only
thing needed to add or change a career path: no code change. Files are re-read automatically when they change on disk.

Recommendation = a transparent score, not a prediction. For each path the student's stage must match; then points are added for
matching stream, interests, skills and goal, and removed if the path usually costs more than the student's budget. The reasons are
returned in plain words so the student can see why a path was suggested.
"""
import glob, json, os

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(HERE, "data", "careers")
BUDGET_RANK = {"low": 0, "medium": 1, "high": 2}
TYPE_LABELS = {
    "stream_choice": "Stream choice", "degree": "Degree", "diploma": "Diploma", "professional": "Professional course",
    "govt_job": "Government job", "private_job": "Private job", "competitive_exam": "Competitive exam",
    "skill": "Skill development", "freelancing": "Freelancing", "entrepreneurship": "Entrepreneurship", "study_abroad": "Study abroad",
}
DEFAULT_FEES_NOTE = ("Fees are not listed here because they change every year and differ by college and state. "
                     "Check the fee structure on the official admission site before you decide.")

_cache = {"stamp": None, "data": None}


def _files():
    return sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))


def _stamp():
    return tuple((f, os.path.getmtime(f)) for f in _files())


def load():
    """Load (and cache) all career data. Reloads by itself when a data file changes."""
    stamp = _stamp()
    if _cache["stamp"] == stamp and _cache["data"]:
        return _cache["data"]
    read = lambda name: json.load(open(os.path.join(DATA_DIR, name), encoding="utf-8"))
    paths = []
    for f in _files():
        if os.path.basename(f).startswith("paths_"):
            paths += json.load(open(f, encoding="utf-8"))
    data = {"questionnaire": read("questionnaire.json"), "guides": read("guides.json"),
            "paths": paths, "by_id": {p["id"]: p for p in paths}}
    _cache.update(stamp=stamp, data=data)
    return data


def summary(p: dict) -> dict:
    return {"id": p["id"], "title": p["title"], "type": p["type"], "type_label": TYPE_LABELS.get(p["type"], p["type"]),
            "stages": p["stages"], "summary": p["summary"], "budget_level": p.get("budget_level")}


def full(p: dict) -> dict:
    out = dict(p)
    out["type_label"] = TYPE_LABELS.get(p["type"], p["type"])
    out["fees_note"] = p.get("fees_note") or DEFAULT_FEES_NOTE
    out.setdefault("app_links", [])
    return out


def stage_guide(stage: str, stream: str | None = None):
    d = load()
    g = d["guides"]["stages"].get(stage)
    if not g:
        return None
    paths = [d["by_id"][i] for i in g["path_ids"] if i in d["by_id"]]
    if stream and stage != "after_10th":
        paths = [p for p in paths if not p.get("streams") or stream in p["streams"] or stream == "other"]
    return {"stage": stage, "title": g["title"], "summary": g["summary"], "key_points": g["key_points"],
            "paths": [summary(p) for p in paths], "disclaimer": d["guides"]["disclaimer"]}


def _labels(question_id: str) -> dict:
    q = next((q for q in load()["questionnaire"]["questions"] if q["id"] == question_id), None)
    return {o["value"]: o["label"] for o in (q or {}).get("options", [])}


def recommend(answers: dict, limit: int = 6) -> list:
    """Return the best-fitting paths for the answers, each with plain-language reasons."""
    d = load()
    stage = answers.get("stage")
    stream = answers.get("stream")
    interests = set(answers.get("interests") or [])
    skills = set(answers.get("skills") or [])
    goal = answers.get("goal")
    budget = answers.get("budget") or "medium"
    il, sl, gl = _labels("interests"), _labels("skills"), _labels("goal")
    results = []
    for order, p in enumerate(d["paths"]):
        if stage and stage not in p["stages"]:
            continue
        score, why, cautions = 0, [], []
        if p.get("streams"):
            if stage == "after_10th" or not stream:
                pass
            elif stream in p["streams"]:
                score += 3; why.append("Fits your stream or field")
            elif stream != "other":
                continue   # a stream-specific path (for example MBBS needs Biology) does not fit another stream
        hit_i = [i for i in p.get("interests", []) if i in interests]
        hit_s = [s for s in p.get("skills", []) if s in skills]
        score += 3 * len(hit_i) + 2 * len(hit_s)
        if hit_i: why.append("Matches your interest in " + ", ".join(il.get(i, i).lower() for i in hit_i))
        if hit_s: why.append("Uses your strengths: " + ", ".join(sl.get(s, s).lower() for s in hit_s))
        if goal and goal != "not_sure" and goal in p.get("goals", []):
            score += 4; why.append("Fits your goal: " + gl.get(goal, goal).lower())
        level = p.get("budget_level", "medium")
        if BUDGET_RANK.get(level, 1) > BUDGET_RANK.get(budget, 1):
            score -= 4
            cautions.append("This path can cost more than you said you can spend. Look at government colleges, scholarships or an education loan.")
        else:
            score += 1
        if not why:
            why.append("A common option at your stage")
        results.append((score, -order, p, why, cautions))
    results.sort(key=lambda r: (r[0], r[1]), reverse=True)
    out = []
    for score, _, p, why, cautions in results[:limit]:
        fit = "Strong fit" if score >= 10 else "Good fit" if score >= 5 else "Worth exploring"
        item = full(p)
        item.update(score=score, fit=fit, why=why, cautions=cautions)
        out.append(item)
    return out
