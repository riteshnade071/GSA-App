"""
Monthly freshness check.   python check_freshness.py            (needs DATABASE_URL, like seed_all.py)
Prints: 1) schemes never verified or not verified for 30+ days   2) deadlines passed / within 14 days
        3) official links that look broken (404/410/5xx/unreachable)    -- pages that block bots (403) are listed as 'check by hand'.
It changes nothing in the database. Then open admin.html, fix whatever is listed, and press Verify.
"""
import urllib.request, urllib.error
from datetime import datetime
from app.database import SessionLocal
from app.models.core import Opportunity

now = datetime.utcnow()
db = SessionLocal()
rows = db.query(Opportunity).order_by(Opportunity.name).all()
print(f"{len(rows)} schemes in database\n")

print("== NOT VERIFIED RECENTLY (never, or 30+ days) ==")
for o in rows:
    age = None if o.last_verified is None else (now - o.last_verified).days
    if age is None or age > 30:
        print(f"- {o.name}: " + ("never verified" if age is None else f"{age} days ago"))

print("\n== DEADLINES ==")
for o in rows:
    if o.deadline:
        d = (o.deadline.date() - now.date()).days
        if d < 0: print(f"- PASSED   {o.name} ({o.deadline:%d %b %Y}) -> edit the deadline if a new cycle opened")
        elif d <= 14: print(f"- {d:>2} days   {o.name} ({o.deadline:%d %b %Y})")

print("\n== OFFICIAL LINKS ==")
seen = {}
for o in rows:
    url = o.official_url
    if url not in seen:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OpportunityHub link check)"})
            seen[url] = f"ok ({urllib.request.urlopen(req, timeout=15).status})"
        except urllib.error.HTTPError as e:
            seen[url] = f"check by hand ({e.code})" if e.code in (401, 403, 405, 429) else f"BROKEN ({e.code})"
        except Exception as e:
            seen[url] = f"UNREACHABLE ({type(e).__name__})"
    if not seen[url].startswith("ok"):
        print(f"- {seen[url]}  {o.name}  {url}")
print("\nDone. (links shown above only if they are not ok)")
db.close()
